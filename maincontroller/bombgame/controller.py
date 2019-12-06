from signal import signal, SIGINT
from asyncio import run, Event
import logging

import can

from .audio import initialize_local_playback
from .bus.bus import BombBus
from .config import BOMB_CASING, CAN_CONFIG
from .gpio import Gpio
from .modules import load_modules
from .utils import FatalError, AuxiliaryThreadExecutor
from .web.server import WebInterface

LOGGER = logging.getLogger("BombGame")


def initialize_can():
    logging.getLogger("CANBus").info("Initializing CAN bus")
    return can.Bus(**CAN_CONFIG)


def init_logging():
    logging.basicConfig(format="%(asctime)s %(levelname)s [%(name)s] %(message)s", level=logging.DEBUG)


def handle_fatal_error(error):
    LOGGER.fatal("Fatal error: %s", error)
    # TODO display a big failure in the UI


def handle_sigint():
    quit_evt = Event()
    signal(SIGINT, lambda _1, _2: quit_evt.set())
    return quit_evt


def init_game():
    init_logging()
    LOGGER.info("Loading modules")
    load_modules()
    initialize_local_playback()


async def wait_for_sigint():
    quit_evt = handle_sigint()
    await quit_evt.wait()


async def run_game(can_bus, gpio, console_interface):
    bus = BombBus(can_bus)
    bus.add_listener(FatalError, handle_fatal_error)
    bus.start()
    web_ui = WebInterface(bus, gpio)
    web_ui.start()
    await console_interface
    web_ui.stop()
    bus.stop()


async def main():
    init_game()
    can_bus = initialize_can()
    gpio = Gpio(BOMB_CASING)
    gpio.start()
    await run_game(can_bus, gpio, wait_for_sigint())
    gpio.stop()

if __name__ == "__main__":
    run(main())
