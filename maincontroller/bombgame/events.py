from __future__ import annotations

from enum import IntEnum
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from bombgame.bomb.bomb import Bomb
    from bombgame.bomb.state import BombState
    from bombgame.modules.base import Module


class TimerTick:
    """The event raised when the bomb timer ticks."""

    def __init__(self, bomb: Bomb):
        self.bomb = bomb

    def __repr__(self):
        return f"<TimerTick>"


class ModuleDefused:
    """The event raised when a module is defused."""

    def __init__(self, module: Module):
        self.module = module

    def __repr__(self):
        return f"<ModuleDefused on {self.module}>"


class ModuleStriked:
    """The event raised when a strike occurs on a module."""

    def __init__(self, module: Module):
        self.module = module

    def __repr__(self):
        return f"<ModuleStriked on {self.module}>"


class BombStateChanged:
    """The event raised when the bomb's state changes."""

    def __init__(self, state: BombState):
        self.state = state

    def __repr__(self):
        return f"<BombStateChanged to {self.state}>"


class BombModuleAdded:
    """The event raised when a module is added to a bomb."""

    def __init__(self, bomb: Bomb, module: Module):
        self.bomb = bomb
        self.module = module

    def __repr__(self):
        return f"<BombModuleAdded: {self.module}>"


class ModuleStateChanged:
    """The event raised when a module's state changes in a way that would require an UI update."""

    def __init__(self, module: Module):
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

    def __init__(self, module: Optional[Module], level: BombErrorLevel, details: str):
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


class BombChanged:
    """The event raised when the game is reset and a new bomb is created."""

    def __init__(self, bomb: Bomb):
        self.bomb = bomb

    def __repr__(self):
        return f"<BombChanged: {self.bomb}>"
