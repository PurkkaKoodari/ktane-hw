from signal import signal, SIGINT
from asyncio import run, Event
from logging import getLogger, basicConfig as logConfig, DEBUG

import can

from .audio import initialize_local_playback
from .bus.bus import BombBus
from .config import BOMB_CASING, CAN_CONFIG
from .gpio import Gpio
from .modules import load_modules
from .utils import FatalError
from .web.server import WebInterface

LOGGER = getLogger("BombGame")


def initialize_can():
    getLogger("CANBus").info("Initializing CAN bus")
    return can.Bus(**CAN_CONFIG)


def init_logging():
    logConfig(format="%(asctime)s %(levelname)s [%(name)s] %(message)s", level=DEBUG)


def handle_fatal_error(error):
    LOGGER.fatal("Fatal error: %s", error)
    # TODO display a big failure in the UI


def handle_sigint():
    quit_evt = Event()
    signal(SIGINT, lambda _1, _2: quit_evt.set())
    return quit_evt


def init_game():
    LOGGER.info("Loading modules")
    load_modules()
    initialize_local_playback()


async def run_game(can_bus, gpio, quit_evt):
    bus = BombBus(can_bus)
    bus.add_listener(FatalError, handle_fatal_error)
    bus.start()
    web_ui = WebInterface(bus, gpio)
    web_ui.start()
    await quit_evt.wait()
    web_ui.stop()
    bus.stop()


async def main():
    init_logging()
    LOGGER.info("Starting. Exit cleanly with SIGINT/Ctrl-C")
    quit_evt = handle_sigint()
    init_game()
    can_bus = initialize_can()
    gpio = Gpio(BOMB_CASING)
    gpio.start()
    await run_game(can_bus, gpio, quit_evt)
    gpio.stop()
    LOGGER.info("Exiting")

if __name__ == "__main__":
    run(main())
