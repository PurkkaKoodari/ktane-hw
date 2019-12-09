from asyncio import run, Event
from logging import getLogger, basicConfig as logConfig, INFO, DEBUG
from signal import signal, SIGINT
from sys import argv

import can

from bombgame.audio import initialize_local_playback
from bombgame.bus.bus import BombBus
from bombgame.config import BOMB_CASING, CAN_CONFIG
from bombgame.gpio import Gpio
from bombgame.modules import load_modules
from bombgame.utils import FatalError
from bombgame.web.server import WebInterface

LOGGER = getLogger("BombGame")


def initialize_can():
    getLogger("CANBus").info("Initializing CAN bus")
    return can.Bus(**CAN_CONFIG)


def init_logging(verbose=False):
    logConfig(format="%(asctime)s %(levelname)s [%(name)s] %(message)s", level=DEBUG if verbose else INFO)
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


async def prepare_game(can_bus=None, gpio=None):
    LOGGER.info("Loading modules")
    load_modules()
    if can_bus is None:
        can_bus = initialize_can()
    if gpio is None:
        gpio = Gpio(BOMB_CASING)
        gpio.start()
    initialize_local_playback()
    bus = BombBus(can_bus)
    bus.add_listener(FatalError, handle_fatal_error)
    bus.start()
    web_ui = WebInterface(bus, gpio)
    await web_ui.start()
    return can_bus, gpio, bus, web_ui


async def cleanup_game(gpio, bus, web_ui):
    await web_ui.stop()
    bus.stop()
    if gpio is not None:
        gpio.stop()


async def main():
    verbose = "-v" in argv
    init_logging(verbose)
    LOGGER.info("Starting. Exit cleanly with SIGINT/Ctrl-C")
    quit_evt = handle_sigint()
    can_bus, gpio, bus, web_ui = await prepare_game()
    await quit_evt.wait()
    await cleanup_game(gpio, bus, web_ui)
    LOGGER.info("Exiting")

if __name__ == "__main__":
    run(main())
