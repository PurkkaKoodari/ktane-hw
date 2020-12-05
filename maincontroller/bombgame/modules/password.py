from __future__ import annotations

import struct
from random import sample
from typing import Sequence, Optional

from bombgame.bus.messages import BusMessage, BusMessageId, BusMessageDirection, ModuleId
from bombgame.modules.base import Module, ModuleState
from bombgame.modules.registry import MODULE_ID_REGISTRY, MODULE_MESSAGE_ID_REGISTRY

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
WORDS = [
    "ABOUT", "AFTER", "AGAIN", "BELOW", "COULD",
    "EVERY", "FIRST", "FOUND", "GREAT", "HOUSE",
    "LARGE", "LEARN", "NEVER", "OTHER", "PLACE",
    "PLANT", "POINT", "RIGHT", "SMALL", "SOUND",
    "SPELL", "STILL", "STUDY", "THEIR", "THERE",
    "THESE", "THING", "THINK", "THREE", "WATER",
    "WHERE", "WHICH", "WORLD", "WOULD", "WRITE"
]

WORD_LENGTH = 5
COLUMN_CHARS = 6


@MODULE_ID_REGISTRY.register
class PasswordModule(Module):
    module_id = 12

    __slots__ = ("_characters", "_solution")

    _characters: Optional[Sequence[Sequence[str]]]
    _solution: Optional[str]

    def __init__(self, bomb, bus_id, location, hw_version, sw_version):
        super().__init__(bomb, bus_id, location, hw_version, sw_version)
        self._characters = None
        self._solution = None

    def generate(self):
        while True:
            characters: Sequence[Sequence[str]] = [sample(ALPHABET, COLUMN_CHARS) for _ in range(WORD_LENGTH)]
            solutions = [word for word in WORDS if all(ch in position for ch, position in zip(word, characters))]
            if len(solutions) == 1:
                self._characters = characters
                self._solution = solutions[0]
                break

    async def send_state(self):
        for pos, column in enumerate(self._characters):
            encoded = "".join(column).encode("ascii")
            await self._bomb.send(PasswordSetCharactersMessage(self.bus_id, position=pos, characters=encoded))

    async def handle_message(self, message: BusMessage):
        if isinstance(message, PasswordSubmitMessage) and self.state in (ModuleState.GAME, ModuleState.DEFUSED):
            if message.word == self._solution.encode("ascii"):
                await self.defuse()
            else:
                await self.strike()
            return True
        return await super().handle_message(message)

    def ui_state(self):
        return {
            "characters": self._characters,
            "solution": self._solution
        }


@MODULE_MESSAGE_ID_REGISTRY.register
class PasswordSetCharactersMessage(BusMessage):
    message_id = (PasswordModule, BusMessageId.MODULE_SPECIFIC_0)

    __slots__ = ("position", "characters",)

    def __init__(self, module: ModuleId, direction: BusMessageDirection = BusMessageDirection.OUT, *,
                 position: int, characters: bytes):
        super().__init__(self.__class__.message_id[1], module, direction)
        if position < 0 or position > WORD_LENGTH:
            raise ValueError(f"position must be between 0 and {WORD_LENGTH}")
        if position == WORD_LENGTH and len(characters) != WORD_LENGTH:
            raise ValueError(f"solution must have {WORD_LENGTH} characters")
        if position < WORD_LENGTH and len(characters) != COLUMN_CHARS:
            raise ValueError(f"column must have {COLUMN_CHARS} characters")
        self.position = position
        self.characters = characters

    @classmethod
    def _parse_data(cls, module: ModuleId, direction: BusMessageDirection, data: bytes):
        if len(data) != COLUMN_CHARS + 1:
            raise ValueError(f"{cls.__name__} must have {COLUMN_CHARS + 1} bytes of data")
        position, = struct.unpack_from("<B", data, 0)
        characters = bytes(data[1:])
        return cls(module, direction, position=position, characters=characters)

    def _serialize_data(self) -> bytes:
        return struct.pack("<B", self.position) + self.characters

    def _data_repr(self) -> str:
        return f"column {self.position + 1}: {self.characters}"


@MODULE_MESSAGE_ID_REGISTRY.register
class PasswordSubmitMessage(BusMessage):
    message_id = (PasswordModule, BusMessageId.MODULE_SPECIFIC_1)

    __slots__ = ("word",)

    def __init__(self, module: ModuleId, direction: BusMessageDirection = BusMessageDirection.OUT, *,
                 word: bytes):
        super().__init__(self.__class__.message_id[1], module, direction)
        self.word = word

    @classmethod
    def _parse_data(cls, module: ModuleId, direction: BusMessageDirection, data: bytes):
        if len(data) != WORD_LENGTH:
            raise ValueError(f"{cls.__name__} must have {WORD_LENGTH} bytes of data")
        word = bytes(data)
        return cls(module, direction, word=word)

    def _serialize_data(self):
        return self.word

    def _data_repr(self):
        return f"{self.word}"
