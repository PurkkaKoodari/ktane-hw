from __future__ import annotations

import struct
from enum import IntEnum
from random import choice, randint, sample

from bombgame.bus.messages import BusMessage, BusMessageId, ModuleId, BusMessageDirection
from bombgame.modules.base import Module
from bombgame.modules.registry import MODULE_ID_REGISTRY, MODULE_MESSAGE_ID_REGISTRY


class WireColor(IntEnum):
    RED = 0
    BLUE = 1
    YELLOW = 2
    BLACK = 3
    WHITE = 4


def _nth(n, rule):
    def matcher(wires):
        matches = []
        for pos, wire in enumerate(wires):
            if rule(wire):
                matches.append(pos)
        return matches[n]
    return matcher


def _nth_wire(n):
    return _nth(n, lambda wire: wire is not None)


def _nth_colored(n, color):
    return _nth(n, lambda wire: wire == color)


RULES = {
    3: [
        (lambda clrs, _: WireColor.RED not in clrs, _nth_wire(1)),
        (lambda clrs, _: clrs[-1] == WireColor.WHITE, _nth_wire(-1)),
        (lambda clrs, _: clrs.count(WireColor.BLUE) > 1, _nth_colored(-1, WireColor.BLUE)),
        (lambda *_: True, _nth_wire(-1))
    ],
    4: [
        (lambda clrs, last_odd: clrs.count(WireColor.RED) > 1 and last_odd, _nth_colored(-1, WireColor.RED)),
        (lambda clrs, _: clrs[-1] == WireColor.YELLOW and WireColor.RED not in clrs, _nth_wire(0)),
        (lambda clrs, _: clrs.count(WireColor.BLUE) == 1, _nth_wire(0)),
        (lambda clrs, _: clrs.count(WireColor.YELLOW) > 1, _nth_wire(-1)),
        (lambda *_: True, _nth_wire(1))
    ],
    5: [
        (lambda clrs, last_odd: clrs[-1] == WireColor.BLACK and last_odd, _nth_wire(3)),
        (lambda clrs, _: clrs.count(WireColor.RED) == 1 and clrs.count(WireColor.YELLOW) > 1, _nth_wire(0)),
        (lambda clrs, _: WireColor.BLACK not in clrs, _nth_wire(1)),
        (lambda *_: True, _nth_wire(0))
    ],
    6: [
        (lambda clrs, last_odd: WireColor.YELLOW not in clrs and last_odd, _nth_wire(2)),
        (lambda clrs, _: clrs.count(WireColor.YELLOW) == 1 and clrs.count(WireColor.WHITE) > 1, _nth_wire(3)),
        (lambda clrs, _: WireColor.RED not in clrs, _nth_wire(-1)),
        (lambda *_: True, _nth_wire(3))
    ]
}


@MODULE_ID_REGISTRY.register
class WiresModule(Module):
    module_id = 2

    __slots__ = ("_wires", "_slots", "_cut", "_solution")

    def __init__(self, bomb, bus_id, location, hw_version, sw_version):
        super().__init__(bomb, bus_id, location, hw_version, sw_version)
        self._wires = None
        self._slots = [None] * 6
        self._cut = [False] * 6
        self._solution = None

    def generate(self):
        count = randint(3, 6)
        self._wires = [choice(list(WireColor.__members__.values())) for _ in range(count)]
        indices = sample(range(6), count)
        for index, color in zip(indices, self._wires):
            self._slots[index] = color
        for condition, rule in RULES[count]:
            if condition(self._wires):
                self._solution = rule(self._slots)
                break
        else:
            raise AssertionError("failed to generate solution")

    async def send_state(self):
        pass

    def ui_state(self):
        return {
            "wires": ["EMPTY" if wire is None else wire.name for wire in self._slots],
            "cut": self._cut,
            "solutions": self._solution
        }

    async def handle_message(self, message: BusMessage):
        if isinstance(message, WiresCutMessage):
            self._cut[message.position] = True
            if message.position == self._solution:
                await self.defuse()
            else:
                await self.strike()
            return True
        return await super().handle_message(message)


@MODULE_MESSAGE_ID_REGISTRY.register
class WiresCutMessage(BusMessage):
    message_id = (WiresModule, BusMessageId.MODULE_SPECIFIC_0)

    __slots__ = ("position",)

    def __init__(self, module: ModuleId, direction: BusMessageDirection = BusMessageDirection.OUT, *,
                 position: int):
        super().__init__(self.__class__.message_id[1], module, direction)
        if not 0 <= position <= 5:
            raise ValueError("position must be between 0 and 5")
        self.position = position

    @classmethod
    def _parse_data(cls, module: ModuleId, direction: BusMessageDirection, data: bytes):
        if len(data) != 1:
            raise ValueError(f"{cls.__name__} must have 1 byte of data")
        position, = struct.unpack("<B", data)
        return cls(module, direction, position=position)

    def _serialize_data(self):
        return struct.pack("<B", self.position)

    def _data_repr(self):
        return f"position {self.position}"
