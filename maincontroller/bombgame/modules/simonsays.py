from enum import IntEnum
from random import randint, choice
from typing import Tuple
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

    __slots__ = ("_sequence",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._sequence = None

    def generate(self):
        length = randint(3, 5)
        self._sequence = [choice(SimonColor.__members__) for _ in range(length)]

@MODULE_MESSAGE_ID_REGISTRY.register
class SetSimonSequenceMessage(BusMessage):
    message_id = (SimonSaysModule, BusMessageId.MODULE_SPECIFIC_0)

    __slots__ = ("sequence",)

    def __init__(self, module: ModuleId, direction: BusMessageDirection = BusMessageDirection.OUT, *,
                 sequence: Tuple[SimonColor]):
        super().__init__(self.__class__.message_id[1], module, direction)
        self.sequence = sequence

    @classmethod
    def _parse_data(cls, module: ModuleId, direction: BusMessageDirection, data: bytes):
        if not 3 <= len(data) <= 5:
            raise ValueError(f"{cls.__name__} must have 3 to 5 bytes of data")
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
        return cls(module, direction, color=SimonColor(data[0]))

    def _serialize_data(self):
        return struct.pack("<B", self.color)
