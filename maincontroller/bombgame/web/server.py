from __future__ import annotations

import json
from asyncio import wait_for, TimeoutError as AsyncTimeoutError
from logging import getLogger
from typing import Optional, Any, Mapping, ClassVar, TYPE_CHECKING, Union

from websockets import WebSocketServerProtocol

from bombgame.bomb.state import BombState
from bombgame.config import WEB_WS_PORT, WEB_PASSWORD, WEB_LOGIN_TIMEOUT
from bombgame.events import BombError, BombModuleAdded, BombStateChanged, ModuleStateChanged, BombChanged
from bombgame.modules.base import Module
from bombgame.utils import EventSource, Registry, Ungettable
from bombgame.websocket import (SingleClientWebSocketServer, InvalidMessage, close_client_invalid_message)

if TYPE_CHECKING:
    from bombgame.controller import BombGameController

MESSAGE_TYPE_REGISTRY = Registry("message_type")

LOGGER = getLogger("WebUI")

# compared against the string sent by the client to identify outdated (cached) UI JS
WEB_UI_VERSION = "0.1-a1"


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
        if not isinstance(json_data, dict):
            raise InvalidMessage("invalid JSON message") from None
        try:
            message_type = json_data["type"]
            message_class = MESSAGE_TYPE_REGISTRY[message_type]
        except KeyError:
            raise InvalidMessage("invalid message type")
        if not message_class.receivable:
            raise InvalidMessage("invalid message type")
        values = {}
        for field, types in message_class.fields.items():
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
    fields = {"ui_version": str, "password": (str, type(None))}
    receivable = True

    def __init__(self, *, ui_version: int, password: Optional[str]):
        super().__init__()
        self.ui_version = ui_version
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
class BombInfoMessage(WebInterfaceMessage):
    message_type = "bomb"
    fields = {"serial_number": str}

    def __init__(self, serial_number: str):
        super().__init__()
        self.serial_number = serial_number


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


async def _parse_message_from_client(client: WebSocketServerProtocol, data: Union[str, bytes]):
    try:
        if not isinstance(data, str):
            raise InvalidMessage("only text messages are valid")
        return WebInterfaceMessage.parse(data)
    except InvalidMessage as error:
        await close_client_invalid_message(client, error.reason)


class WebInterface(EventSource, SingleClientWebSocketServer):
    _controller: BombGameController

    def __init__(self, controller: BombGameController):
        EventSource.__init__(self)
        SingleClientWebSocketServer.__init__(self)
        self._controller = controller

    async def _send(self, message: WebInterfaceMessage, client: Optional[WebSocketServerProtocol] = None):
        await self._send_to_client(message.serialize(), client)

    async def _new_client_connected(self, client: WebSocketServerProtocol):
        try:
            data = await wait_for(client.recv(), WEB_LOGIN_TIMEOUT)
            handshake = await _parse_message_from_client(client, data)
        except AsyncTimeoutError:
            handshake = None

        if not isinstance(handshake, LoginMessage):
            await close_client_invalid_message(client, "must send login message upon connecting")
        if handshake.ui_version != WEB_UI_VERSION:
            await close_client_invalid_message(client, "web ui version mismatch", 4001)
        if WEB_PASSWORD is not None:
            if handshake.password is None:
                await close_client_invalid_message(client, "password is required", 4003)
            if handshake.password != WEB_PASSWORD:
                await close_client_invalid_message(client, "password is incorrect", 4003)

        # TODO send current state
        await self._send(ConfigMessage({}), client)
        await self._send(BombInfoMessage(self._controller.bomb.edgework.serial_number), client)
        for module in self._controller.bomb.modules:
            await self._send_module(module, client)
        await self._send(StateMessage(self._controller.bomb._state.name), client)

    async def _bomb_changed(self, event: BombChanged):
        await self._send(ResetMessage())
        await self._send(BombInfoMessage(event.bomb.edgework.serial_number))
        event.bomb.add_listener(BombModuleAdded, self._handle_module_add)
        event.bomb.add_listener(BombStateChanged, self._handle_bomb_state)
        event.bomb.add_listener(ModuleStateChanged, self._handle_module_update)
        event.bomb.add_listener(BombError, self._log_bomb_error)

    async def _handle_message(self, client: WebSocketServerProtocol, data: Union[str, bytes]):
        message = await _parse_message_from_client(client, data)
        if isinstance(message, ResetMessage):
            self._controller.reset()
        elif isinstance(message, ConfigMessage):
            # TODO
            await close_client_invalid_message(client, "config not implemented")
        elif isinstance(message, StartGameMessage):
            if self._controller.bomb._state == BombState.INITIALIZED:
                self._controller.bomb.start_game()
        else:
            await close_client_invalid_message(client, "invalid message type")

    async def _send_module(self, module: Module, client: Optional[WebSocketServerProtocol] = None):
        await self._send(AddModuleMessage(
            location=module.location,
            module_type=module.bus_id.type,
            serial=module.bus_id.serial,
            state=module.state.name,
            error_level=module.error_level.name,
            details=module.ui_state()
        ), client)

    async def _log_bomb_error(self, error: BombError):
        await self._send(ErrorMessage(error.level.name, error.location, error.details))

    async def _handle_bomb_state(self, event: BombStateChanged):
        if event.state != BombState.DEINITIALIZED:
            await self._send(StateMessage(event.state.name))

    async def _handle_module_add(self, event: BombModuleAdded):
        await self._send_module(event.module)

    async def _handle_module_update(self, event: ModuleStateChanged):
        await self._send(UpdateModuleMessage(
            location=event.module.location,
            state=event.module.state.name,
            details=event.module.ui_state()
        ))

    async def start(self):
        LOGGER.info("Starting Web UI")
        await self.start_server(WEB_WS_PORT)

    async def stop(self):
        LOGGER.info("Stopping Web UI")
        await self.stop_server()


async def initialize_web_ui(controller: BombGameController) -> WebInterface:
    web_ui = WebInterface(controller)
    await web_ui.start()
    return web_ui
