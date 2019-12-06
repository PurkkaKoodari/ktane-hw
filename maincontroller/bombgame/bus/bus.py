from __future__ import annotations
from logging import getLogger
from asyncio import create_task, wrap_future
import time

import can

from .messages import BusMessage
from ..config import CAN_ERROR_MAX_COUNT, CAN_ERROR_MAX_INTERVAL
from ..utils import EventSource, AuxiliaryThreadExecutor, FatalError

LOGGER = getLogger("BombBus")


class BombBus(EventSource):
    """The CAN-based bus used for controlling the physical bomb.

    Listen for suitable BusMessage events to get incoming messages.
    """

    def __init__(self, can_bus: can.BusABC):
        super().__init__()
        self._can_bus = can_bus
        self._last_can_error = time.monotonic()
        self._can_error_count = 0
        self._error_limit_exceeded = False
        self._send_executor = AuxiliaryThreadExecutor(name="CANSender")
        self._receive_executor = AuxiliaryThreadExecutor(name="CANReceiver")
        self._receiver = None

    def start(self):
        if self._receiver is not None:
            raise RuntimeError("bus already started")
        LOGGER.info("Starting bus receiver")
        self._receive_executor.start()
        self._send_executor.start()
        self._receiver = create_task(self._receive_loop())

    def stop(self):
        if self._receiver is None:
            raise RuntimeError("bus not started")
        LOGGER.info("Stopping bus receiver")
        self._receiver.cancel()
        self._receive_executor.shutdown(True)
        self._send_executor.shutdown(True)

    async def _receive_loop(self):
        while True:
            await wrap_future(self._receive_executor.submit(self._sync_receive))

    def _sync_receive(self):
        try:
            message = self._can_bus.recv(1)
            if message is not None:
                try:
                    message = BusMessage.parse(message)
                except ValueError as ex:
                    self._handle_bus_error()
                    LOGGER.error("Invalid message from CAN: %s", ex)
                else:
                    self.trigger(message)
        except can.CanError as ex:
            LOGGER.error("I/O error receiving message from CAN: %s", ex, exc_info=True)

    async def send(self, message: BusMessage):
        """Send a message to the bus."""
        await wrap_future(self._send_executor.submit(self._sync_send, message))

    def _sync_send(self, message: BusMessage):
        try:
            self._can_bus.send(message.serialize())
        except can.CanError as ex:
            self._handle_bus_error()
            LOGGER.error("I/O error sending message to CAN: %s", ex, exc_info=True)

    def _handle_bus_error(self):
        if time.monotonic() > self._last_can_error + CAN_ERROR_MAX_INTERVAL:
            self._last_can_error = time.monotonic()
            self._can_error_count = 1
        else:
            self._can_error_count += 1
        if not self._error_limit_exceeded and self._can_error_count >= CAN_ERROR_MAX_COUNT:
            self._error_limit_exceeded = True
            self.trigger(FatalError(f"received {self._can_error_count} CAN errors in {CAN_ERROR_MAX_INTERVAL} seconds"))
