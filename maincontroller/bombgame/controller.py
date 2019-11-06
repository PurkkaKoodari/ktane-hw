import asyncio
import logging

import can

from .audio import initialize_local_playback
from .bus.bus import BombBus
from .casings import VanillaCasing
from .gpio import Gpio
from .modules import load_modules
from .utils import FatalError, AuxiliaryThreadExecutor

def initialize_can():
    logging.getLogger("CANBus").info("Initializing CAN bus")
    # TODO configuration for this
    return can.Bus(interface="virtual", channel="mock")
    # return can.Bus(interface="socketcan", channel="can0")

def init_logging():
    logging.basicConfig(format="%(asctime)s %(levelname)s [%(name)s] %(message)s", level=logging.DEBUG)

def handle_fatal_error(error):
    logging.getLogger("BombGame").fatal("Fatal error: %s", error)
    # TODO display a big failure in the UI

# TODO move to configuration
CASING = VanillaCasing()

async def main():
    init_logging()
    logging.getLogger("BombGame").info("Loading modules")
    load_modules()
    initialize_local_playback()
    can_bus = initialize_can()
    gpio = Gpio(CASING)
    gpio.start()
    bus = BombBus(can_bus)
    bus.add_listener(FatalError, handle_fatal_error)
    bus.start()
    audio_thread = AuxiliaryThreadExecutor(name="AudioPlayer")
    audio_thread.start()
    # TODO do stuff
    audio_thread.shutdown(True)
    bus.stop()
    gpio.stop()

if __name__ == "__main__":
    asyncio.run(main())
