from __future__ import annotations

import struct
from enum import IntEnum, Enum
from random import sample
from typing import Sequence, Optional, Iterable, List

from bombgame.bus.messages import BusMessage, BusMessageId, ModuleId, BusMessageDirection
from bombgame.modules.base import Module, ModuleState
from bombgame.modules.registry import MODULE_ID_REGISTRY, MODULE_MESSAGE_ID_REGISTRY


class KeypadPosition(IntEnum):
    TOP_LEFT = 0
    TOP_RIGHT = 1
    BOTTOM_LEFT = 2
    BOTTOM_RIGHT = 3


class KeypadSymbol(Enum):
    COPYRIGHT = "©"
    PILCROW = "¶"
    QUESTION = "¿"
    AE = "æ"
    LAMBDA = "ƛ"
    PSI = "Ψ"
    OMEGA = "Ω"
    KAI = "ϗ"
    ARCHAIC_KOPPA = "Ϙ"
    KOPPA = "Ϟ"
    SHIMA = "Ϭ"
    C = "Ͼ"
    REVERSE_C = "Ͽ"
    YAT = "Ѣ"
    LITTLE_YUS = "Ѧ"
    IOTIFIED_YUS = "Ѭ"
    KSI = "Ѯ"
    OMEGA_TITLO = "Ѽ"
    THOUSANDS = "҂"
    I_TAIL = "Ҋ"
    ZHE = "Җ"
    HA = "Ҩ"
    E_DIAERESIS = "Ӭ"
    KOMI_DZJE = "Ԇ"
    TEH = "ټ"
    BLACK_STAR = "★"
    WHITE_STAR = "☆"


KEYPAD_COLUMNS = [
    [KeypadSymbol.ARCHAIC_KOPPA, KeypadSymbol.LITTLE_YUS, KeypadSymbol.LAMBDA, KeypadSymbol.KOPPA, KeypadSymbol.IOTIFIED_YUS, KeypadSymbol.KAI, KeypadSymbol.REVERSE_C],
    [KeypadSymbol.E_DIAERESIS, KeypadSymbol.ARCHAIC_KOPPA, KeypadSymbol.REVERSE_C, KeypadSymbol.HA, KeypadSymbol.WHITE_STAR, KeypadSymbol.KAI, KeypadSymbol.QUESTION],
    [KeypadSymbol.COPYRIGHT, KeypadSymbol.OMEGA_TITLO, KeypadSymbol.HA, KeypadSymbol.ZHE, KeypadSymbol.KOMI_DZJE, KeypadSymbol.LAMBDA, KeypadSymbol.WHITE_STAR],
    [KeypadSymbol.SHIMA, KeypadSymbol.PILCROW, KeypadSymbol.YAT, KeypadSymbol.IOTIFIED_YUS, KeypadSymbol.ZHE, KeypadSymbol.QUESTION, KeypadSymbol.TEH],
    [KeypadSymbol.PSI, KeypadSymbol.TEH, KeypadSymbol.YAT, KeypadSymbol.C, KeypadSymbol.PILCROW, KeypadSymbol.KSI, KeypadSymbol.BLACK_STAR],
    [KeypadSymbol.SHIMA, KeypadSymbol.E_DIAERESIS, KeypadSymbol.THOUSANDS, KeypadSymbol.AE, KeypadSymbol.PSI, KeypadSymbol.I_TAIL, KeypadSymbol.OMEGA]
]


@MODULE_ID_REGISTRY.register
class KeypadModule(Module):
    module_id = 4

    __slots__ = ("_buttons", "_solution")

    _buttons: Optional[Sequence[KeypadSymbol]]
    _solution: Optional[Sequence[KeypadPosition]]
    _pressed: List[KeypadPosition]

    def __init__(self, bomb, bus_id, location, hw_version, sw_version):
        super().__init__(bomb, bus_id, location, hw_version, sw_version)
        self._buttons = None
        self._solution = None
        self._pressed = []

    def generate(self):
        while True:
            buttons: Sequence[KeypadSymbol] = sample(list(KeypadSymbol.__members__.values()), 4)
            solutions = [column for column in KEYPAD_COLUMNS if all(key in column for key in buttons)]
            if len(solutions) == 1:
                self._buttons = buttons
                self._solution = [KeypadPosition(buttons.index(key)) for key in solutions[0] if key in buttons]
                break

    async def send_state(self):
        pass

    async def handle_message(self, message: BusMessage):
        if isinstance(message, KeypadPressMessage) and self.state in (ModuleState.GAME, ModuleState.DEFUSED):
            if message.position in self._pressed:
                # ignore already-pressed buttons
                pass
            elif len(self._pressed) < len(self._solution) and message.position == self._solution[len(self._pressed)]:
                self._pressed.append(message.position)
                await self._bomb.send(KeypadSetLedsMessage(self.bus_id, leds=self._pressed))
                if len(self._pressed) == len(self._solution):
                    await self.defuse()
            else:
                await self.strike()
            return True
        return await super().handle_message(message)

    def ui_state(self):
        if self._buttons is None:
            return {}
        return {
            "buttons": [symbol.value for symbol in self._buttons],
            "solution": [position.name for position in self._solution],
            "pressed": [position.name for position in self._pressed],
        }


@MODULE_MESSAGE_ID_REGISTRY.register
class KeypadPressMessage(BusMessage):
    message_id = (KeypadModule, BusMessageId.MODULE_SPECIFIC_0)

    __slots__ = ("position",)

    def __init__(self, module: ModuleId, direction: BusMessageDirection = BusMessageDirection.OUT, *,
                 position: KeypadPosition):
        super().__init__(self.__class__.message_id[1], module, direction)
        self.position = position

    @classmethod
    def _parse_data(cls, module: ModuleId, direction: BusMessageDirection, data: bytes):
        if len(data) != 1:
            raise ValueError(f"{cls.__name__} must have 1 byte of data")
        position, = struct.unpack("<B", data)
        return cls(module, direction, position=KeypadPosition(position))

    def _serialize_data(self):
        return struct.pack("<B", self.position.value)

    def _data_repr(self):
        return self.position.name


@MODULE_MESSAGE_ID_REGISTRY.register
class KeypadSetLedsMessage(BusMessage):
    message_id = (KeypadModule, BusMessageId.MODULE_SPECIFIC_1)

    __slots__ = ("leds",)

    def __init__(self, module: ModuleId, direction: BusMessageDirection = BusMessageDirection.OUT, *,
                 leds: Iterable[KeypadPosition]):
        super().__init__(self.__class__.message_id[1], module, direction)
        self.leds = set(leds)

    @classmethod
    def _parse_data(cls, module: ModuleId, direction: BusMessageDirection, data: bytes):
        if len(data) != 1:
            raise ValueError(f"{cls.__name__} must have 1 byte of data")
        bitfield, = struct.unpack("<B", data)
        leds = (pos for pos in KeypadPosition.__members__.values() if bitfield & (1 << pos.value))
        return cls(module, direction, leds=leds)

    def _serialize_data(self):
        return struct.pack("<B", sum(1 << pos.value for pos in self.leds))

    def _data_repr(self):
        return ", ".join(pos.name for pos in self.leds) or "none"
