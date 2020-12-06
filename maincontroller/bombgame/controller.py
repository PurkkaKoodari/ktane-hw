from asyncio import Task, create_task
from logging import getLogger
from typing import Optional

import can

from bombgame.audio import BombSoundSystem
from bombgame.bomb.bomb import Bomb
from bombgame.bus.bus import BombBus
from bombgame.config import BOMB_CASING, CAN_CONFIG, ROOM_SERVER
from bombgame.dmx import DMXController, initialize_bomb_dmx
from bombgame.events import BombChanged
from bombgame.gpio import Gpio, AbstractGpio
from bombgame.modules import load_modules
from bombgame.roomserver.client import RoomServerClient
from bombgame.utils import FatalError, EventSource, log_errors
from bombgame.web.server import WebInterface, initialize_web_ui

LOGGER = getLogger("BombGame")


def initialize_can() -> can.BusABC:
    getLogger("CANBus").info("Initializing CAN bus")
    return can.Bus(**CAN_CONFIG)


def handle_fatal_error(error):
    LOGGER.fatal("Fatal error: %s", error)
    # TODO display a big failure in the UI


class BombGameController(EventSource):
    can_bus: Optional[can.BusABC]
    gpio: Optional[AbstractGpio]
    sound_system: Optional[BombSoundSystem]
    bus: Optional[BombBus]
    web_ui: Optional[WebInterface]
    room_server: Optional[RoomServerClient]
    dmx: Optional[DMXController]
    bomb: Optional[Bomb]
    _bomb_init_task: Optional[Task]

    def __init__(self, can_bus: Optional[can.BusABC] = None, gpio: Optional[AbstractGpio] = None):
        super().__init__()
        self.can_bus = can_bus
        self.gpio = gpio
        self.sound_system = None
        self.bus = None
        self.web_ui = None
        self.dmx = None
        self.bomb = None
        self._bomb_init_task = None

    async def _initialize_bomb(self):
        self.bomb = Bomb(self.bus, self.gpio, self.sound_system, BOMB_CASING)
        self.trigger(BombChanged(self.bomb))
        self._bomb_init_task = create_task(self.bomb.initialize())
        await self._bomb_init_task
        self._bomb_init_task = None

    def _deinitialize_bomb(self):
        if self._bomb_init_task:
            self._bomb_init_task.cancel()
        self._bomb_init_task = None
        if self.bomb:
            self.bomb.deinitialize()

    async def start(self):
        LOGGER.info("Loading modules")
        load_modules()
        if self.can_bus is None:
            self.can_bus = initialize_can()
        if self.gpio is None:
            self.gpio = Gpio(BOMB_CASING)
            self.gpio.start()
        if ROOM_SERVER is not None:
            self.room_server = RoomServerClient()
            await self.room_server.start()
        self.sound_system = BombSoundSystem(self.room_server)
        await self.sound_system.start()
        self.bus = BombBus(self.can_bus)
        self.bus.add_listener(FatalError, handle_fatal_error)
        self.bus.start()
        self.web_ui = await initialize_web_ui(self)
        self.dmx = await initialize_bomb_dmx(self)
        create_task(log_errors(self._initialize_bomb()))

    async def stop(self):
        self._deinitialize_bomb()
        if self.dmx is not None:
            await self.dmx.stop()
        await self.web_ui.stop()
        self.bus.stop()
        if self.sound_system is not None:
            self.sound_system.stop()  # TODO wrap in executor?
        if self.room_server is not None:
            await self.room_server.stop()
        if self.gpio is not None:
            self.gpio.stop()  # TODO wrap in executor?
        if self.can_bus is not None:
            self.can_bus.shutdown()

    def reset(self):
        self._deinitialize_bomb()
        create_task(log_errors(self._initialize_bomb()))
