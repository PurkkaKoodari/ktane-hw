from random import choice
from typing import Optional

LETTERS = "ABCDEFGHIJKLMNPQRSTUVWXZ"
NUMBERS = "0123456789"
BOTH = LETTERS + NUMBERS

VOWELS = "AEIOU"
CONSONANTS = "BCDFGHJKLMNPQRSTVWXYZ"
ODD = "13579"
EVEN = "02468"


def _generate_serial():
    return choice(BOTH) + choice(BOTH) + choice(NUMBERS) + choice(LETTERS) + choice(LETTERS) + choice(NUMBERS)


class BombSerial(str):
    def __init__(self, serial: Optional[str] = None):
        super().__init__(_generate_serial() if serial is None else serial)

    def has(self, chars):
        return any(char in self for char in chars)

    def last_is(self, chars):
        return self[5] in chars
