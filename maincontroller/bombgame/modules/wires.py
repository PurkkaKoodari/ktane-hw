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
    DISCONNECTED = 5
    SHORT = 6
    INVALID = 7


REAL_COLORS = (WireColor.RED, WireColor.BLUE, WireColor.YELLOW, WireColor.BLACK, WireColor.WHITE)


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

    __slots__ = ("_initial_connected", "_cut", "_connected", "_solution")

    def __init__(self, bomb, bus_id, location, hw_version, sw_version):
        super().__init__(bomb, bus_id, location, hw_version, sw_version)
        self._initial_connected = None
        self._cut = [False] * 6
        self._initial_connected = [WireColor.DISCONNECTED] * 6
        self._connected = [WireColor.DISCONNECTED] * 6
        self._solution = None
        bomb.add_listener(BombStateChanged, self._handle_bomb_state)

    def generate(self):
        last_odd = self._bomb.edgework.serial_number.last_is(ODD)
        count = randint(3, 6)
        colors = [choice(REAL_COLORS) for _ in range(count)]
        indices = sample(range(6), count)
        for index, color in zip(indices, colors):
            self._initial_connected[index] = color
        for condition, rule in RULES[count]:
            if condition(colors, last_odd):
                self._solution = rule(self._initial_connected)
                break
        else:
            raise AssertionError("failed to generate solution")

    async def send_state(self):
        pass

    def ui_state(self):
        if self._solution is None:
            return {}
        return {
            "wires": [wire.name for wire in self._initial_connected],
            "connected": [wire.name for wire in self._connected],
            "cut": self._cut,
            "solution": self._solution,
        }

    def _handle_bomb_state(self, event: BombStateChanged):
        if event.state == BombState.GAME_STARTING:
            bad_pos = [str(pos) for pos in range(6) if self._initial_connected[pos] != self._connected[pos]]
            if bad_pos:
                self._bomb.trigger(BombError(self, BombErrorLevel.MAJOR,
                                             f"The wires in positions {', '.join(bad_pos)} do not match the initial "
                                             f"state, potentially making the module unsolvable."))

    async def handle_message(self, message: BusMessage):
        if isinstance(message, WiresUpdateMessage):
            prev_connected = self._connected
            self._connected = list(message.wires)
            if self.state in (ModuleState.GAME, ModuleState.DEFUSED):
                for pos in range(6):
                    # a wire is disconnected when it:
                    if (not self._cut[pos]  # hasn't been cut yet
                            and self._initial_connected[pos] != WireColor.DISCONNECTED  # is supposed to exist
                            and prev_connected[pos] != WireColor.DISCONNECTED  # did exist a moment ago
                            and self._connected[pos] == WireColor.DISCONNECTED):  # no longer exists
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
class WiresUpdateMessage(BusMessage):
    message_id = (WiresModule, BusMessageId.MODULE_SPECIFIC_0)

    wires: Sequence[WireColor]

    def __init__(self, module: ModuleId, direction: BusMessageDirection = BusMessageDirection.OUT, *,
                 wires: Sequence[WireColor]):
        super().__init__(self.__class__.message_id[1], module, direction)
        if len(wires) != 6:
            raise ValueError("must have 6 wires")
        self.wires = tuple(wires)

    @classmethod
    def _parse_data(cls, module: ModuleId, direction: BusMessageDirection, data: bytes):
        if len(data) != 6:
            raise ValueError(f"{cls.__name__} must have 6 bytes of data")
        wires = [WireColor(wire) for wire in struct.unpack("<6B", data)]
        return cls(module, direction, wires=wires)

    def _serialize_data(self):
        return struct.pack("<6B", self.wires)

    def _data_repr(self):
        return " ".join(wire.name for wire in self.wires)
