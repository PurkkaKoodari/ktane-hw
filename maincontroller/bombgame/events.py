from enum import IntEnum
from typing import Optional


class TimerTick:
    """The event raised when the bomb timer ticks."""

    __slots__ = ()

    def __repr__(self):
        return f"<TimerTick>"


class ModuleStriked:
    """The event raised when a strike occurs on a module."""

    __slots__ = ("module",)

    def __init__(self, module):
        self.module = module

    def __repr__(self):
        return f"<ModuleStriked on {self.module}>"


class BombStateChanged:
    """The event raised when the bomb's state changes."""

    __slots__ = ("state",)

    def __init__(self, state):
        self.state = state

    def __repr__(self):
        return f"<BombStateChanged to {self.state}>"


class BombModuleAdded:
    """The event raised when a module is added to a bomb."""

    __slots__ = ("module",)

    def __init__(self, module):
        self.module = module

    def __repr__(self):
        return f"<BombModuleAdded: {self.module}>"


class ModuleStateChanged:
    """The event raised when a module's state changes in a way that would require an UI update."""

    __slots__ = ("module",)

    def __init__(self, module):
        self.module = module

    def __repr__(self):
        return f"<ModuleStateChanged in {self.module}>"


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

    def __repr__(self):
        if self.module is None:
            return f"<BombError {self.level.name}: {self.details}>"
        return f"<BombError {self.level.name} in {self.module}: {self.details}>"

    @property
    def location(self):
        return None if self.module is None else self.module.location
