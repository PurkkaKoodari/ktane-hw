from abc import ABC, abstractmethod
from asyncio import create_task, get_event_loop, Future, Event, wait, Task
from logging import getLogger
from typing import Optional, Dict, Sequence, TYPE_CHECKING

from websockets import connect, WebSocketClientProtocol

from bombgame.bomb.state import BombState
from bombgame.config import DMX_SERVER
from bombgame.events import BombStateChanged, TimerTick, BombChanged
from bombgame.utils import log_errors

if TYPE_CHECKING:
    from bombgame.controller import BombGameController

LOGGER = getLogger("DMX")


class DMXBackend(ABC):
    async def start(self):
        """Starts background tasks for the DMX backend. The default implementation does nothing."""

    async def stop(self):
        """Stops backend tasks started by ``start()``. The default implementation does nothing."""

    @abstractmethod
    def change_scene(self, scene: str):
        """Changes the scene to the given one."""


class QLCPlusApi:
    _pending_requests: Dict[str, Future[Sequence[str]]]
    _connection: Optional[WebSocketClientProtocol]

    def __init__(self, url: str):
        self._url = url
        self._pending_requests = {}
        self._connection = None
        self._closing = False

    async def start(self):
        if self._closing or self._connection is not None:
            raise RuntimeError("already started or stopped")
        self._connection = await connect(self._url)
        create_task(log_errors(self._client_receiver()))

    async def stop(self):
        self._closing = True
        if self._connection is not None:
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
                self._pending_requests[action].set_result(results)
        finally:
            self._connection = None

    async def call(self, action: str, *params: str) -> Sequence[str]:
        if self._connection is None:
            raise RuntimeError("QLC+ API client not started yet")
        if action in self._pending_requests:
            raise ValueError(f"request {action} already pending")
        future = self._pending_requests[action] = get_event_loop().create_future()
        await self._connection.send(f"QLC+API|" + "|".join([action, *params]))
        return await future
        

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
            scene_ids[function_id] = name

        missing_scenes = set(ALL_SCENES) - set(scene_ids.keys())
        if missing_scenes:
            LOGGER.error("Missing scenes in QLC+: %s", ", ".join(missing_scenes))
            return

        # turn off all relevant scenes
        for scene in ALL_SCENES:
            await self._api.call("setFunctionStatus", scene_ids[scene], "0")

        current_scene = None
        while True:
            await self._change_event.wait()
            self._change_event.clear()
            next_scene = self._next_scene

            if next_scene == current_scene:
                continue

            futures = []
            if current_scene is not None:
                futures.append(self._api.call("setFunctionStatus", scene_ids[current_scene], "0"))
            futures.append(self._api.call("setFunctionStatus", scene_ids[next_scene], "1"))

            # wait for both calls and ensure we raise any errors
            done, _ = await wait(futures)
            for future in done:
                future.result()

            current_scene = next_scene

    def change_scene(self, scene: str):
        self._next_scene = scene
        self._change_event.set()


SCENE_BEFORE_START = "Before Start"
SCENE_NORMAL = "Normal"
SCENE_EMERGENCY = "Emergency"
SCENE_EXPLOSION = "Explosion"
SCENE_VICTORY = "Success"
ALL_SCENES = (SCENE_BEFORE_START, SCENE_NORMAL, SCENE_EMERGENCY, SCENE_EXPLOSION, SCENE_VICTORY)

EMERGENCY_SECONDS = 60


class DMXController:
    _backend: DMXBackend

    def __init__(self, controller: BombGameController):
        self._backend = QLCPlusDMXBackend()
        controller.add_listener(BombChanged, self._bomb_changed)

    async def start(self):
        await self._backend.start()

    async def stop(self):
        await self._backend.stop()

    def _bomb_changed(self, event: BombChanged):
        event.bomb.add_listener(BombStateChanged, self._bomb_state_change)
        event.bomb.add_listener(TimerTick, self._timer_tick)

    def _bomb_state_change(self, event: BombStateChanged):
        if event.state == BombState.INITIALIZED:
            # TODO: trigger this based on reset, not init completing
            self._backend.change_scene(SCENE_NORMAL)
        elif event.state == BombState.GAME_STARTING:
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