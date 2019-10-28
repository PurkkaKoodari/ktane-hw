import logging

import can

from .audio import initialize_local_playback
from .bus.bus import BombBus
from .modules import load_modules
from .utils import FatalError, AuxiliaryThreadExecutor

def initialize_can():
    can_bus = can.Bus(interface="socketcan", channel="can0") # TODO configuration for this
    return can_bus

def init_logging():
    logging.basicConfig(format="%(asctime)s %(levelname)s [%(name)s] %(message)s", level=logging.DEBUG)

def handle_fatal_error(source, error):
    logging.getLogger("BombGame").fatal("Fatal error from %s: %s", source.__class__.__name__, error)
    # TODO display a big failure in the UI

def main():
    init_logging()
    load_modules()
    initialize_local_playback()
    can_bus = initialize_can()
    bus = BombBus(can_bus)
    bus.add_listener(FatalError, handle_fatal_error)
    bus.start()
    audio_thread = AuxiliaryThreadExecutor(name="AudioPlayer")
    audio_thread.start()
    # TODO do stuff
    audio_thread.shutdown(True)
    bus.stop(True)

if __name__ == "__main__":
    main()
