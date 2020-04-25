from __future__ import annotations

from random import choice
from typing import Iterable

LETTERS = "ABCDEFGHIJKLMNPQRSTUVWXZ"
NUMBERS = "0123456789"
BOTH = LETTERS + NUMBERS

VOWELS = "AEIOU"
CONSONANTS = "BCDFGHJKLMNPQRSTVWXYZ"
ODD = "13579"
EVEN = "02468"


def _generate_serial() -> str:
    return choice(BOTH) + choice(BOTH) + choice(NUMBERS) + choice(LETTERS) + choice(LETTERS) + choice(NUMBERS)


class BombSerial(str):
    @classmethod
    def generate(cls) -> BombSerial:
        return cls(_generate_serial())

    def has(self, chars: Iterable[str]) -> bool:
        return any(char in self for char in chars)

    def last_is(self, chars: Iterable[str]) -> bool:
        return self[5] in chars
