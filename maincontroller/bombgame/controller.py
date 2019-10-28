import logging

import can

from .audio import initialize_local_playback
from .bus import BombBus, BusError
from .modules import load_modules
from .utils import AuxiliaryThread

def initialize_can():
    can_bus = can.Bus() # TODO configuration for this
    return can_bus

class CanReceiverThread(AuxiliaryThread):
    def __init__(self, can_bus: can.BusABC, bus: BombBus):
        super().__init__(name="CanReceiver")
        self.can_bus = can_bus
        self.bus = bus

    def _run(self):
        logger = logging.getLogger("CanReceiver")
        while not self._quit:
            try:
                message = self.can_bus.recv(1.0)
                if message is not None:
                    self.bus.receive(message)
            except BusError as ex:
                logger.error("invalid message received: %s", ex)

def init_logging():
    logging.basicConfig(format="%(asctime)s %(levelname)s [%(name)s] %(message)s", level=logging.DEBUG)

def run():
    init_logging()
    load_modules()
    initialize_local_playback()
    can_bus = initialize_can()
    bus = BombBus(can_bus)
    can_thread = CanReceiverThread(can_bus, bus)
    can_thread.start()

if __name__ == "__main__":
    run()
