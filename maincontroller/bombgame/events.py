from enum import IntEnum
from typing import Optional


class TimerTick:
    """The event raised when the bomb timer ticks."""

    __slots__ = ()


class BombStateChange:
    """The event raised when the bomb's state changes."""

    __slots__ = ("state",)

    def __init__(self, state):
        self.state = state


class BombModuleAdded:
    """The event raised when a module is added to a bomb."""

    __slots__ = ("module",)

    def __init__(self, module):
        self.module = module


class ModuleStateChange:
    """The event raised when a module's state changes."""

    __slots__ = ("module",)

    def __init__(self, module):
        self.module = module


class BombErrorLevel(IntEnum):
    NONE = 0
    INFO = 1
    RECOVERED = 2
    WARNING = 3
    RECOVERABLE = 4
    MINOR = 5
    MAJOR = 6
    INIT_FAILURE = 7
    FATAL = 8


class BombError:
    """The event raised when an error occurs in the bomb or a module."""

    __slots__ = ("module", "level", "details")

    def __init__(self, module: Optional, level: BombErrorLevel, details: str):
        self.module = module
        self.level = level
        self.details = details

    @property
    def location(self):
        return None if self.module is None else self.module.location
