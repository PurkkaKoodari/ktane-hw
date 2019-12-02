from __future__ import annotations
from asyncio import create_task, wait_for, Task
from typing import Optional, Any, Mapping, ClassVar
import json

from websockets import serve, WebSocketServerProtocol, ConnectionClosed

from ..bomb.bomb import Bomb
from bombgame.bomb.state import BombState
from ..bus.bus import BombBus
from ..config import BOMB_CASING
from ..events import BombError, BombModuleAdded, BombStateChanged, ModuleStateChanged
from ..gpio import Gpio
from ..modules.base import Module
from ..utils import EventSource, Registry, Ungettable

MESSAGE_TYPE_REGISTRY = Registry("message_type")


class InvalidMessage(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class WebInterfaceMessage:
    message_type: ClassVar[str] = Ungettable
    fields: ClassVar[Mapping[str, Any]] = Ungettable
    receivable: ClassVar[bool] = False

    @staticmethod
    def parse(data: str) -> "WebInterfaceMessage":
        try:
            json_data = json.loads(data)
        except json.JSONDecodeError:
            raise InvalidMessage("invalid JSON message") from None
        if not isinstance(data, dict):
            raise InvalidMessage("invalid JSON message") from None
        try:
            message_type = json_data["type"]
            message_class = MESSAGE_TYPE_REGISTRY[message_type]
        except KeyError:
            raise InvalidMessage("invalid message type")
        if not message_class.receivable:
            raise InvalidMessage("invalid message type")
        values = {}
        for field, types in message_class.fields.values():
            try:
                value = json_data[field]
            except KeyError:
                raise InvalidMessage(f"missing value for {field}")
            if not isinstance(value, types):
                raise InvalidMessage(f"invalid value for {field}")
            values[field] = value
        return message_class(**values)

    def serialize(self) -> str:
        return json.dumps({
            "type": self.__class__.message_type,
            **{field: getattr(self, field) for field in self.__class__.fields}
        })


@MESSAGE_TYPE_REGISTRY.register
class LoginMessage(WebInterfaceMessage):
    message_type = "login"
    fields = {"ui_version": str, "password": str}

    def __init__(self, *, ui_version: int, password: str):
        super().__init__()
        self.location = ui_version
        self.type = password


@MESSAGE_TYPE_REGISTRY.register
class ResetMessage(WebInterfaceMessage):
    message_type = "reset"
    fields = {}
    receivable = True


@MESSAGE_TYPE_REGISTRY.register
class StartGameMessage(WebInterfaceMessage):
    message_type = "start_game"
    fields = {}
    receivable = True


@MESSAGE_TYPE_REGISTRY.register
class PauseGameMessage(WebInterfaceMessage):
    message_type = "pause_game"
    fields = {}
    receivable = True


@MESSAGE_TYPE_REGISTRY.register
class UnpauseGameMessage(WebInterfaceMessage):
    message_type = "unpause_game"
    fields = {}
    receivable = True


@MESSAGE_TYPE_REGISTRY.register
class StateMessage(WebInterfaceMessage):
    message_type = "state"
    fields = {"state": str}

    def __init__(self, state: str):
        super().__init__()
        self.state = state


@MESSAGE_TYPE_REGISTRY.register
class AddModuleMessage(WebInterfaceMessage):
    message_type = "add_module"
    fields = {"location": int, "module_type": int, "serial": int, "state": str, "error_level": str, "details": (dict, type(None))}

    def __init__(self, *, location: int, module_type: int, serial: int, state: str, error_level: str, details: Optional[Mapping[str, Any]]):
        super().__init__()
        self.location = location
        self.module_type = module_type
        self.serial = serial
        self.state = state
        self.error_level = error_level
        self.details = details


@MESSAGE_TYPE_REGISTRY.register
class UpdateModuleMessage(WebInterfaceMessage):
    message_type = "update_module"
    fields = {"location": int, "state": str, "details": dict}

    def __init__(self, *, location: int, state: str, details: Mapping[str, Any]):
        super().__init__()
        self.location = location
        self.state = state
        self.details = details


@MESSAGE_TYPE_REGISTRY.register
class ConfigMessage(WebInterfaceMessage):
    message_type = "config"
    fields = {"config": dict}
    receivable = True

    def __init__(self, config: Mapping[str, Any]):
        super().__init__()
        self.config = config


@MESSAGE_TYPE_REGISTRY.register
class ErrorMessage(WebInterfaceMessage):
    message_type = "error"
    fields = {"level": str, "module": (int, type(None)), "message": str}

    def __init__(self, level: str, module: Optional[int], message: str):
        super().__init__()
        self.level = level
        self.module = module
        self.message = message


# TODO move to config
WEB_UI_VERSION = "0.1-a1"
WEB_PASSWORD = None
WEB_LOGIN_TIMEOUT = 2


async def _invalid_message(client: WebSocketServerProtocol, reason: str = "invalid message", code: int = 1003):
    await client.close(code, reason)
    raise ConnectionClosed(code, reason) from None


async def _receive(client: WebSocketServerProtocol):
    try:
        data = await client.recv()
        if not isinstance(data, str):
            raise InvalidMessage("only text messages are valid")
        return WebInterfaceMessage.parse(data)
    except InvalidMessage as error:
        await _invalid_message(client, error.reason)


class WebInterface(EventSource):
    __slots__ = ("_bus", "_gpio", "_bomb", "_serve_task", "_client")

    _serve_task: Optional[Task]
    _client: Optional[WebSocketServerProtocol]
    _bomb: Optional[Bomb]
    _bomb_init_task: Optional[Task]

    def __init__(self, bus: BombBus, gpio: Gpio):
        super().__init__()
        self._bus = bus
        self._gpio = gpio
        self._serve_task = None
        self._bomb = None
        self._client = None
        self._bomb_init_task = None

    async def _send_to_client(self, message: WebInterfaceMessage, client: Optional[WebSocketServerProtocol] = None):
        if client is None:
            client = self._client
        if client is not None:
            try:
                await client.send(message.serialize())
            except ConnectionClosed:
                pass

    async def _handle_client(self, client: WebSocketServerProtocol, path: str):
        try:
            handshake: LoginMessage = await wait_for(_receive(client), WEB_LOGIN_TIMEOUT)
            if not isinstance(handshake, LoginMessage):
                await _invalid_message(client, "must send login-message upon connecting")
            if handshake.ui_version != WEB_UI_VERSION:
                await _invalid_message(client, "web ui version mismatch", 4001)
            if WEB_PASSWORD is not None:
                if handshake.password is None:
                    await _invalid_message(client, "password is required", 4002)
                if handshake.password != WEB_PASSWORD:
                    await _invalid_message(client, "password is incorrect", 4003)
            # TODO send current state
            # await self._send_to_client(ConfigMessage(whatever), client)
            # for module in self._bomb.modules:
            #     await self._send_module(module, client)
            # await self._send_to_client(StateMessage(whatever), client)
        except ConnectionClosed:
            return
        old_client = self._client
        self._client = client
        if old_client:
            await old_client.close(4000)
        try:
            while True:
                await self._handle_message(client, await _receive(client))
        except ConnectionClosed:
            if client is self._client:
                self._client = None
            return

    async def _handle_message(self, client, message):
        if isinstance(message, ResetMessage):
            self._bomb.deinitialize()
            create_task(self._initialize_bomb())
        elif isinstance(message, ConfigMessage):
            # TODO
            await _invalid_message(client, "config not implemented")
        else:
            await _invalid_message(client, "invalid message type")

    async def _send_module(self, module: Module, client: Optional[WebSocketServerProtocol] = None):
        await self._send_to_client(AddModuleMessage(
            location=module.location,
            module_type=module.bus_id.type,
            serial=module.bus_id.serial,
            state=module.state,
            error_level=module.error_level.name,
            details=module.ui_state()
        ), client)

    async def _log_bomb_error(self, error: BombError):
        await self._send_to_client(ErrorMessage(error.level.name, error.location, error.details))

    async def _handle_bomb_state(self, event: BombStateChanged):
        if event.state != BombState.DEINITIALIZED:
            await self._send_to_client(StateMessage(event.state.name))

    async def _handle_module_add(self, event: BombModuleAdded):
        await self._send_module(event.module)

    async def _handle_module_update(self, event: ModuleStateChanged):
        await self._send_to_client(UpdateModuleMessage(
            location=event.module.location,
            state=event.module.state.name,
            details=event.module.ui_state()
        ))

    async def _initialize_bomb(self):
        await self._send_to_client(ResetMessage())
        self._bomb = Bomb(self._bus, self._gpio, BOMB_CASING)
        self._bomb.add_listener(BombModuleAdded, self._handle_module_add)
        self._bomb.add_listener(BombStateChanged, self._handle_bomb_state)
        self._bomb.add_listener(ModuleStateChanged, self._handle_module_update)
        self._bomb.add_listener(BombError, self._log_bomb_error)
        self._bomb_init_task = create_task(self._bomb.initialize())
        await self._bomb_init_task
        self._bomb_init_task = None

    def _deinitialize_bomb(self):
        if self._bomb_init_task:
            self._bomb_init_task.cancel()
        self._bomb_init_task = None
        if self._bomb:
            self._bomb.deinitialize()

    def start(self):
        if self._serve_task is not None:
            raise RuntimeError("web interface already running")
        self._serve_task = create_task(serve(self._handle_client))
        create_task(self._initialize_bomb())

    def stop(self):
        if self._serve_task is None:
            raise RuntimeError("web interface is not running")
        self._serve_task.cancel()
        self._deinitialize_bomb()
