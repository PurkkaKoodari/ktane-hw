from asyncio import run, Event, Task, create_task
from logging import getLogger, INFO, DEBUG, StreamHandler, Formatter, LogRecord
from signal import signal, SIGINT
from sys import argv
from typing import Optional

import can

from bombgame.audio import initialize_local_playback
from bombgame.bomb.bomb import Bomb
from bombgame.bus.bus import BombBus
from bombgame.config import BOMB_CASING, CAN_CONFIG
from bombgame.events import BombChanged
from bombgame.gpio import Gpio, AbstractGpio
from bombgame.modules import load_modules
from bombgame.utils import FatalError, EventSource, log_errors
from bombgame.web.server import WebInterface

LOGGER = getLogger("BombGame")

NOISY_EVENTS = {"PingMessage", "TimerTick"}


def filter_noisy_log(record: LogRecord):
    if record.name == "EventSource" and len(record.args) >= 1 and type(record.args[0]).__name__ in NOISY_EVENTS:
        return False
    if record.name == "ModulePing" and record.levelno == DEBUG:
        return False
    return True


def initialize_can() -> can.BusABC:
    getLogger("CANBus").info("Initializing CAN bus")
    return can.Bus(**CAN_CONFIG)


def init_logging(verbose=False):
    handler = StreamHandler()
    handler.addFilter(filter_noisy_log)
    handler.setFormatter(Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    getLogger().setLevel(DEBUG if verbose else INFO)
    getLogger().addHandler(handler)
    if verbose:
        getLogger("websockets").setLevel(INFO)
        getLogger("can").setLevel(INFO)


def handle_fatal_error(error):
    LOGGER.fatal("Fatal error: %s", error)
    # TODO display a big failure in the UI


def handle_sigint():
    quit_evt = Event()
    signal(SIGINT, lambda _1, _2: quit_evt.set())
    return quit_evt


class BombGameController(EventSource):
    can_bus: Optional[can.BusABC]
    gpio: Optional[AbstractGpio]
    bus: Optional[BombBus]
    web_ui: Optional[WebInterface]
    bomb: Optional[Bomb]
    _bomb_init_task: Optional[Task]

    def __init__(self, can_bus: Optional[can.BusABC] = None, gpio: Optional[AbstractGpio] = None):
        super().__init__()
        self.can_bus = can_bus
        self.gpio = gpio
        self.bus = None
        self.web_ui = None
        self.bomb = None
        self._bomb_init_task = None

    async def _initialize_bomb(self):
        self.bomb = Bomb(self.bus, self.gpio, BOMB_CASING)
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
        initialize_local_playback()
        self.bus = BombBus(self.can_bus)
        self.bus.add_listener(FatalError, handle_fatal_error)
        self.bus.start()
        self.web_ui = WebInterface(self)
        await self.web_ui.start()
        create_task(log_errors(self._initialize_bomb()))

    async def stop(self):
        self._deinitialize_bomb()
        await self.web_ui.stop()
        self.bus.stop()
        if self.gpio is not None:
            self.gpio.stop()
        if self.can_bus is not None:
            self.can_bus.shutdown()

    def reset(self):
        self._deinitialize_bomb()
        create_task(log_errors(self._initialize_bomb()))


async def main():
    verbose = "-v" in argv
    init_logging(verbose)
    LOGGER.info("Starting. Exit cleanly with SIGINT/Ctrl-C")
    quit_evt = handle_sigint()
    game = BombGameController()
    await game.start()
    await quit_evt.wait()
    await game.stop()
    LOGGER.info("Exiting")

if __name__ == "__main__":
    run(main())
