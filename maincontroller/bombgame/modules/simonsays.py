from __future__ import annotations
from enum import IntEnum
from random import randint, choice
from typing import Sequence
import struct

from .base import Module
from .registry import MODULE_ID_REGISTRY, MODULE_MESSAGE_ID_REGISTRY
from ..bus.messages import BusMessage, BusMessageId, ModuleId, BusMessageDirection

class SimonColor(IntEnum):
    BLUE = 0
    YELLOW = 1
    GREEN = 2
    RED = 3

@MODULE_ID_REGISTRY.register
class SimonSaysModule(Module):
    module_id = 5

    __slots__ = ("_sequence", "_length", "_pressed")

    def __init__(self, bomb, bus_id, location, hw_version, sw_version):
        super().__init__(bomb, bus_id, location, hw_version, sw_version)
        self._sequence = None
        self._length = 1
        self._pressed = []
        bomb.bus.add_listener(SimonButtonPressMessage, self._handle_event)

    def generate(self):
        length = randint(3, 5)
        self._sequence = [choice(SimonColor.__members__) for _ in range(length)]

    async def prepare(self):
        await self._send_sequence()

    async def _send_sequence(self):
        await self._bomb.bus.send(SetSimonSequenceMessage(self.bus_id, sequence=self._sequence[:self._length]))

    async def _handle_event(self, event: SimonButtonPressMessage):
        self._pressed.append(event.color)
        if self._pressed != self._sequence[:len(self._pressed)]:
            await self.strike()
            self._pressed = []
        elif self._length == len(self._sequence):
            await self.solve()
        else:
            self._length += 1
            await self._send_sequence()

@MODULE_MESSAGE_ID_REGISTRY.register
class SetSimonSequenceMessage(BusMessage):
    message_id = (SimonSaysModule, BusMessageId.MODULE_SPECIFIC_0)

    __slots__ = ("sequence",)

    def __init__(self, module: ModuleId, direction: BusMessageDirection = BusMessageDirection.OUT, *,
                 sequence: Sequence[SimonColor]):
        super().__init__(self.__class__.message_id[1], module, direction)
        self.sequence = sequence

    @classmethod
    def _parse_data(cls, module: ModuleId, direction: BusMessageDirection, data: bytes):
        if not 1 <= len(data) <= 5:
            raise ValueError(f"{cls.__name__} must have 1 to 5 bytes of data")
        sequence = tuple(SimonColor(byte) for byte in data)
        return cls(module, direction, sequence=sequence)

    def _serialize_data(self):
        return b"".join(struct.pack("<B", color) for color in self.sequence)

@MODULE_MESSAGE_ID_REGISTRY.register
class SimonButtonPressMessage(BusMessage):
    message_id = (SimonSaysModule, BusMessageId.MODULE_SPECIFIC_1)

    __slots__ = ("color",)

    def __init__(self, module: ModuleId, direction: BusMessageDirection = BusMessageDirection.OUT, *,
                 color: SimonColor):
        super().__init__(self.__class__.message_id[1], module, direction)
        self.color = color

    @classmethod
    def _parse_data(cls, module: ModuleId, direction: BusMessageDirection, data: bytes):
        if len(data) != 1:
            raise ValueError(f"{cls.__name__} must have 1 byte of data")
        color, = struct.unpack("<B", data)
        return cls(module, direction, color=SimonColor(color))

    def _serialize_data(self):
        return struct.pack("<B", self.color)
