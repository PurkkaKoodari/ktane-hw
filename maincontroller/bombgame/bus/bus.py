from __future__ import annotations
import time

import can

from .messages import BusMessage
from ..utils import EventSource, AuxiliaryThread, FatalError

class BusError(Exception):
    """An exception related to the bus."""

class CanReceiverThread(AuxiliaryThread):
    def __init__(self, can_bus: can.BusABC, bus: BombBus):
        super().__init__(name="CanReceiver")
        self._can_bus = can_bus
        self._bus = bus

    def _run(self):
        while not self._quit:
            try:
                message = self._can_bus.recv(1)
                if message is not None:
                    self._bus._receive(message)
            except can.CanError as ex:
                self.logger.error("I/O error receiving message from CAN: %s", ex, exc_info=True)
            except BusError as ex:
                self.logger.error("Invalid message from CAN: %s", ex)

# if we encounter 10 errors in 15 seconds, raise a fatal error
# TODO move to a config file
CAN_ERROR_MAX_INTERVAL = 15
CAN_ERROR_MAX_COUNT = 10

class BombBus(EventSource):
    """The CAN-based bus used for controlling the physical bomb.

    Listen for suitable BusMessage events to get incoming messages.
    """

    def __init__(self, can_bus: can.BusABC):
        super().__init__()
        self._can_bus = can_bus
        self._receiver = CanReceiverThread(can_bus, self)
        self._last_can_error = time.monotonic()
        self._can_error_count = 0
        self._error_limit_exceeded = False
        self.add_listener(BusError, self._handle_bus_error)

    def send(self, message: BusMessage):
        """Send a message to the bus."""
        try:
            self._can_bus.send(message.serialize())
        except can.CanError:
            self.trigger(BusError("failed to send message"))
            raise IOError("failed to send message") from None

    def _receive(self, message: can.Message) -> None:
        """Called by the CAN receiver thread when a message arrives."""
        try:
            message = BusMessage.parse(message)
        except ValueError as ex:
            self.trigger(BusError(f"invalid CAN message: {ex}"))
            raise BusError(f"invalid CAN message: {ex}") from None
        else:
            self.trigger(message)

    def _handle_bus_error(self, _1, _2):
        if time.monotonic() > self._last_can_error + CAN_ERROR_MAX_INTERVAL:
            self._last_can_error = time.monotonic()
            self._can_error_count = 1
        else:
            self._can_error_count += 1
        if not self._error_limit_exceeded and self._can_error_count >= CAN_ERROR_MAX_COUNT:
            self._error_limit_exceeded = True
            self.trigger(FatalError(f"received {self._can_error_count} CAN errors in {CAN_ERROR_MAX_INTERVAL} seconds"))

    def start(self):
        self._receiver.start()

    def stop(self, wait=True):
        self._receiver.stop()
        if wait:
            self._receiver.join()
