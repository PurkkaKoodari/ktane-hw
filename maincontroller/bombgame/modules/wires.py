from __future__ import annotations

import struct
from enum import IntEnum
from logging import getLogger
from random import choice, randint, sample
from typing import Sequence

from bombgame.bomb.serial import ODD
from bombgame.bomb.state import BombState
from bombgame.bus.messages import BusMessage, BusMessageId, ModuleId, BusMessageDirection
from bombgame.events import BombStateChanged, BombError, BombErrorLevel, ModuleStateChanged
from bombgame.modules.base import Module, ModuleState
from bombgame.modules.registry import MODULE_ID_REGISTRY, MODULE_MESSAGE_ID_REGISTRY

LOGGER = getLogger("Wires")


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
        self._connected = [False] * 6
        self._solution = None
        bomb.add_listener(BombStateChanged, self._handle_bomb_state)

    def generate(self):
        last_odd = self._bomb.serial_number.last_is(ODD)
        count = randint(3, 6)
        self._wires = [choice(list(WireColor.__members__.values())) for _ in range(count)]
        indices = sample(range(6), count)
        for index, color in zip(indices, self._wires):
            self._slots[index] = color
        for condition, rule in RULES[count]:
            if condition(self._wires, last_odd):
                self._solution = rule(self._slots)
                break
        else:
            raise AssertionError("failed to generate solution")

    async def send_state(self):
        pass

    def ui_state(self):
        return {
            "wires": ["EMPTY" if wire is None else wire.name for wire in self._slots],
            "connected": self._connected,
            "solutions": self._solution
        }

    def _handle_bomb_state(self, event: BombStateChanged):
        if event.state == BombState.GAME_STARTING:
            bad_pos = [str(pos) for pos in range(6) if self._slots[pos] is not None and not self._connected[pos]]
            if bad_pos:
                self._bomb.trigger(BombError(self, BombErrorLevel.MAJOR,
                                             f"The wires in positions {', '.join(bad_pos)} are not connected, "
                                             f"making the module unsolvable."))

    async def handle_message(self, message: BusMessage):
        if isinstance(message, WiresSetPositionsMessage):
            was_connected = self._connected
            self._connected = [pos in message.positions for pos in range(6)]
            if self.state in (ModuleState.GAME, ModuleState.DEFUSED):
                for pos in range(6):
                    if self._slots[pos] is not None and not self._cut[pos] and was_connected[pos] and not self._connected[pos]:
                        self._cut[pos] = True
                        if pos == self._solution:
                            LOGGER.info("Wire %s cut correctly", pos + 1)
                            await self.defuse()
                        else:
                            LOGGER.info("Wire %s cut, expecting %s", pos + 1, self._solution + 1)
                            if await self.strike():
                                return
            self._bomb.trigger(ModuleStateChanged(self))
            return True
        return await super().handle_message(message)


@MODULE_MESSAGE_ID_REGISTRY.register
class WiresSetPositionsMessage(BusMessage):
    message_id = (WiresModule, BusMessageId.MODULE_SPECIFIC_0)

    positions: Sequence[int]

    def __init__(self, module: ModuleId, direction: BusMessageDirection = BusMessageDirection.OUT, *,
                 positions: Sequence[int]):
        super().__init__(self.__class__.message_id[1], module, direction)
        if len(positions) != len(set(positions)):
            raise ValueError("positions must be unique")
        if not all(0 <= position < 6 for position in positions):
            raise ValueError("positions must be between 0 and 5")
        self.positions = tuple(positions)

    @classmethod
    def _parse_data(cls, module: ModuleId, direction: BusMessageDirection, data: bytes):
        if len(data) != 1:
            raise ValueError(f"{cls.__name__} must have 1 byte of data")
        bitfield, = struct.unpack("<B", data)
        positions = [i for i in range(6) if bitfield & (1 << i)]
        return cls(module, direction, positions=positions)

    def _serialize_data(self):
        return struct.pack("<B", sum(1 << position for position in self.positions))

    def _data_repr(self):
        return "connected: " + " ".join(str(position + 1) for position in sorted(self.positions))
