from __future__ import annotations

from abc import ABC, abstractmethod
from asyncio import create_task, get_event_loop, Future, Event, Task
from logging import getLogger
from typing import Optional, Dict, Sequence, TYPE_CHECKING

from websockets import connect, WebSocketClientProtocol, ConnectionClosed

from bombgame.bomb.state import BombState
from bombgame.config import DMX_SERVER, ROOM_SERVER, ROOM_DMX_ENABLED
from bombgame.events import BombStateChanged, TimerTick, BombChanged
from bombgame.roomserver.common import RoomServerChannel
from bombgame.roomserver.client import RoomServerClient
from bombgame.utils import log_errors
from bombgame.websocket import InvalidMessage

if TYPE_CHECKING:
    from bombgame.controller import BombGameController
    from bombgame.roomserver.server import RoomServer

LOGGER = getLogger("DMX")

SCENE_BEFORE_START = "Before Start"
SCENE_NORMAL = "Normal"
SCENE_EMERGENCY = "Emergency"
SCENE_EXPLOSION = "Explosion"
SCENE_VICTORY = "Success"
ALL_SCENES = (SCENE_BEFORE_START, SCENE_NORMAL, SCENE_EMERGENCY, SCENE_EXPLOSION, SCENE_VICTORY)

EMERGENCY_SECONDS = 60


class DMXBackend(ABC):
    async def start(self):
        """Starts background tasks for the DMX backend. The default implementation does nothing."""

    async def stop(self):
        """Stops backend tasks started by ``start()``. The default implementation does nothing."""

    @abstractmethod
    def change_scene(self, scene: str):
        """Changes the scene to the given one."""

    def add_room_server_handler(self, room_server: RoomServer):
        room_server.add_handler(RoomServerChannel.DMX, self._handle_dmx_message)

    async def _handle_dmx_message(self, data: dict):
        scene = data.get("scene")
        if not isinstance(scene, str):
            raise InvalidMessage("invalid scene")
        if scene not in ALL_SCENES:
            raise InvalidMessage(f"unknown scene {scene}")
        self.change_scene(scene)


class QLCPlusApi:
    _url: str
    _pending_requests: Dict[str, Future[Sequence[str]]]
    _connection: Optional[WebSocketClientProtocol]
    _close_requested: bool

    def __init__(self, url: str):
        self._url = url
        self._pending_requests = {}
        self._connection = None
        self._close_requested = False

    async def start(self):
        if self._close_requested or self._connection is not None:
            raise RuntimeError("already started or stopped")
        LOGGER.info("Connecting to QLC+ API")
        self._connection = await connect(self._url, ping_interval=None, ping_timeout=None)
        create_task(log_errors(self._client_receiver()))

    async def stop(self):
        self._close_requested = True
        if self._connection is not None:
            LOGGER.info("Closing QLC+ API connection")
            await self._connection.close()
            self._connection = None

    async def _client_receiver(self):
        try:
            async for message in self._connection:
                if isinstance(message, bytes):
                    LOGGER.warning("Binary message from QLC+")
                    continue
                parts = message.split("|")
                if len(parts) < 2:
                    LOGGER.warning("Too short message from QLC+")
                    continue
                header, action, *results = parts
                if header != "QLC+API":
                    LOGGER.warning("Unknown message prefix from QLC+")
                    continue
                if action not in self._pending_requests:
                    LOGGER.warning("Response from QLC+ to %s without matching request", action)
                    continue
                LOGGER.debug("Response from QLC+ to %s", action)
                self._pending_requests.pop(action).set_result(results)
        except ConnectionClosed as ex:
            if not self._close_requested:
                LOGGER.error("QLC+ API connection closed unexpectedly (code %s)", ex.code)
        finally:
            self._connection = None

    async def call(self, action: str, *params: str, expect_response: Optional[bool] = None) -> Optional[Sequence[str]]:
        expect_response = expect_response is True or (expect_response is None and action.startswith("get"))
        if self._connection is None:
            raise RuntimeError("QLC+ API client not started yet")
        if action in self._pending_requests:
            raise ValueError(f"request {action} already pending")
        if expect_response:
            future = self._pending_requests[action] = get_event_loop().create_future()
        LOGGER.debug("Request %s to QLC+", action)
        await self._connection.send(f"QLC+API|" + "|".join([action, *params]))
        if expect_response:
            return await future
        else:
            return None
        

class QLCPlusDMXBackend(DMXBackend):
    _api: QLCPlusApi
    _next_scene: Optional[str]
    _change_event: Event
    _background_task: Optional[Task]

    def __init__(self):
        self._api = QLCPlusApi(DMX_SERVER)
        self._next_scene = None
        self._change_event = Event()
        self._background_task = None

    async def start(self):
        await self._api.start()
        self._background_task = create_task(log_errors(self._background()))

    async def stop(self):
        if self._background_task is not None:
            self._background_task.cancel()
        await self._api.stop()

    async def _background(self):
        function_list = await self._api.call("getFunctionsList")

        ids = function_list[0::2]
        names = function_list[1::2]
        scene_ids = {}
        for function_id, name in zip(ids, names):
            scene_ids[name] = function_id

        missing_scenes = set(ALL_SCENES) - set(scene_ids.keys())
        if missing_scenes:
            LOGGER.error("Missing scenes in QLC+: %s", ", ".join(missing_scenes))
            return

        # turn off all relevant scenes
        LOGGER.debug("Turning off all scenes")
        for scene in ALL_SCENES:
            await self._api.call("setFunctionStatus", scene_ids[scene], "0")

        current_scene = None
        while True:
            await self._change_event.wait()
            self._change_event.clear()
            next_scene = self._next_scene

            if next_scene == current_scene:
                LOGGER.debug("Current scene is already %s", next_scene)
                continue

            LOGGER.debug("Changing scene to %s", next_scene)
            if current_scene is not None:
                await self._api.call("setFunctionStatus", scene_ids[current_scene], "0")
            await self._api.call("setFunctionStatus", scene_ids[next_scene], "1")

            current_scene = next_scene

    def change_scene(self, scene: str):
        self._next_scene = scene
        self._change_event.set()


class RoomServerDMXBackend(DMXBackend):
    def __init__(self, room_server: RoomServerClient):
        self._room_server = room_server

    def change_scene(self, scene: str):
        self._room_server.send_async(RoomServerChannel.DMX, {"scene": scene})


class DMXController:
    _backend: DMXBackend

    def __init__(self, controller: BombGameController, backend: DMXBackend):
        self._backend = backend
        controller.add_listener(BombChanged, self._bomb_changed)

    async def start(self):
        LOGGER.info("Starting DMX controller")
        await self._backend.start()

    async def stop(self):
        LOGGER.info("Stopping DMX controller")
        await self._backend.stop()

    def _bomb_changed(self, event: BombChanged):
        event.bomb.add_listener(BombStateChanged, self._bomb_state_change)
        event.bomb.add_listener(TimerTick, self._timer_tick)
        self._backend.change_scene(SCENE_NORMAL)

    def _bomb_state_change(self, event: BombStateChanged):
        if event.state == BombState.GAME_STARTING:
            self._backend.change_scene(SCENE_BEFORE_START)
        elif event.state == BombState.GAME_STARTED:
            self._backend.change_scene(SCENE_NORMAL)
        elif event.state == BombState.DEFUSED:
            self._backend.change_scene(SCENE_VICTORY)
        elif event.state == BombState.EXPLODED:
            self._backend.change_scene(SCENE_EXPLOSION)

    def _timer_tick(self, event: TimerTick):
        if event.bomb._state == BombState.GAME_STARTED and event.bomb.time_left < EMERGENCY_SECONDS:
            self._backend.change_scene(SCENE_EMERGENCY)


def initialize_local_dmx_backend() -> Optional[DMXBackend]:
    if DMX_SERVER is not None:
        return QLCPlusDMXBackend()
    else:
        return None


async def initialize_bomb_dmx(controller: BombGameController) -> Optional[DMXController]:
    """Chooses a DMX backend based on configuration and starts the controller based on it."""
    if ROOM_SERVER is not None and ROOM_DMX_ENABLED:
        backend = RoomServerDMXBackend(controller.room_server)
    else:
        backend = initialize_local_dmx_backend()
    if backend is None:
        return None
    controller = DMXController(controller, backend)
    await controller.start()
    return controller
