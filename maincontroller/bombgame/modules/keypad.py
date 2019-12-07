from __future__ import annotations

import struct
from enum import IntEnum
from random import sample
from typing import Sequence

from bombgame.bus.messages import BusMessage, BusMessageId, ModuleId, BusMessageDirection
from bombgame.modules.base import Module
from bombgame.modules.registry import MODULE_ID_REGISTRY, MODULE_MESSAGE_ID_REGISTRY


class KeypadButton(IntEnum):
    TOP_LEFT = 0
    TOP_RIGHT = 1
    BOTTOM_LEFT = 2
    BOTTOM_RIGHT = 3


class KeypadSymbol(IntEnum):
    COPYRIGHT = 0  # ©
    PILCROW = 1  # ¶
    QUESTION = 2  # ¿
    AE = 3  # æ
    LAMBDA = 4  # ƛ
    PSI = 5  # Ψ
    OMEGA = 6  # Ω
    KAI = 7  # ϗ
    ARCHAIC_KOPPA = 8  # Ϙ
    KOPPA = 9  # Ϟ
    SHIMA = 10  # Ϭ
    C = 11  # Ͼ
    REVERSE_C = 12  # Ͽ
    YAT = 13  # Ѣ
    LITTLE_YUS = 14  # Ѧ
    IOTIFIED_YUS = 15  # Ѭ
    KSI = 16  # Ѯ
    OMEGA_TITLO = 17  # Ѽ
    THOUSANDS = 18  # ҂
    I_TAIL = 19  # Ҋ
    ZHE = 20  # Җ
    HA = 21 # Ҩ
    E_DIAERESIS = 22  # Ӭ
    KOMI_DZJE = 23  # Ԇ
    TEH = 24  # ټ
    BLACK_STAR = 25  # ★
    WHITE_STAR = 26  # ☆


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

    def __init__(self, bomb, bus_id, location, hw_version, sw_version):
        super().__init__(bomb, bus_id, location, hw_version, sw_version)
        self._buttons = None
        self._solution = None
        bomb.bus.add_listener(KeypadEventMessage, self._handle_event)

    def generate(self):
        while True:
            buttons = sample(KeypadSymbol.__members__, 4)
            solutions = [column for column in KEYPAD_COLUMNS if all(key in column for key in buttons)]
            if len(solutions) == 1:
                self._buttons = buttons
                self._solution = [key for key in solutions[0] if key in buttons]

    async def send_state(self):
        await self._bomb.bus.send(KeypadSetSolutionMessage(self.bus_id, sequence=self._solution))

    def ui_state(self):
        return {
            "buttons": [button.name for button in self._buttons],
            "solution": self._solution
        }

    async def _handle_event(self, event: KeypadEventMessage):
        if event.correct:
            await self.defuse()
        else:
            await self.strike()


@MODULE_MESSAGE_ID_REGISTRY.register
class KeypadSetSolutionMessage(BusMessage):
    message_id = (KeypadModule, BusMessageId.MODULE_SPECIFIC_0)

    __slots__ = ("sequence",)

    def __init__(self, module: ModuleId, direction: BusMessageDirection = BusMessageDirection.OUT, *,
                 sequence: Sequence[KeypadButton]):
        super().__init__(self.__class__.message_id[1], module, direction)
        self.sequence = sequence

    @classmethod
    def _parse_data(cls, module: ModuleId, direction: BusMessageDirection, data: bytes):
        if len(data) != 4:
            raise ValueError(f"{cls.__name__} must have 4 bytes of data")
        sequence = tuple(KeypadButton(byte) for byte in data)
        return cls(module, direction, sequence=sequence)

    def _serialize_data(self):
        return b"".join(struct.pack("<B", button) for button in self.sequence)

    def _data_repr(self):
        return " ".join(button.name for button in self.sequence)


@MODULE_MESSAGE_ID_REGISTRY.register
class KeypadEventMessage(BusMessage):
    message_id = (KeypadModule, BusMessageId.MODULE_SPECIFIC_1)

    __slots__ = ("correct",)

    def __init__(self, module: ModuleId, direction: BusMessageDirection = BusMessageDirection.OUT, *,
                 correct: bool):
        super().__init__(self.__class__.message_id[1], module, direction)
        self.correct = correct

    @classmethod
    def _parse_data(cls, module: ModuleId, direction: BusMessageDirection, data: bytes):
        if len(data) != 1:
            raise ValueError(f"{cls.__name__} must have 1 byte of data")
        return cls(module, direction, correct=bool(data[0]))

    def _serialize_data(self):
        return struct.pack("<B", self.correct)

    def _data_repr(self):
        return "correct" if self.correct else "incorrect"
