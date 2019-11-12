from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum
from time import monotonic
from typing import Tuple, List

from ..bus.messages import StrikeModuleMessage, SolveModuleMessage, ModuleId, ErrorMessage, RecoveredErrorMessage
from ..events import BombError, BombErrorLevel, ModuleStateChange

DEFAULT_ERROR_DESCRIPTIONS = {
    0: "The module received an invalid message.",
    1: "The module encountered an unknown hardware error.",
    2: "The module encountered an unknown software error."
}

UNKNOWN_ERROR_DESCRIPTION = "The module encountered an unknown error."


class ModuleState(Enum):
    INITIALIZATION = 1
    CONFIGURATION = 2
    GAME = 3
    DEFUSED = 4


class Module(ABC):
    """
    The base class for modules.
    """

    __slots__ = ("_bomb", "bus_id", "location", "hw_version", "sw_version", "last_received", "last_ping_sent", "state", "errors")

    is_needy = False
    is_boss = False

    errors: List[Tuple[int, BombError]]

    def __init__(self, bomb, bus_id: ModuleId, location: int, hw_version: Tuple[int], sw_version: Tuple[int]):
        self._bomb = bomb
        self.bus_id = bus_id
        self.location = location
        self.hw_version = hw_version
        self.sw_version = sw_version
        self.last_received = self.last_ping_sent = monotonic()
        self.state = ModuleState.INITIALIZATION
        self.errors = []
        bomb.add_listener(ErrorMessage, self._track_error_state)

    def _track_error_state(self, message: ErrorMessage):
        if isinstance(message, RecoveredErrorMessage):
            for code, existing in self.errors:
                if code == message.code:
                    self.errors.remove((code, existing))
        error = BombError(self, message.error_level, self._describe_error(message))
        self.errors.append((message.code, error))
        self._bomb.trigger(error)

    def _describe_error(self, error: ErrorMessage):
        try:
            return DEFAULT_ERROR_DESCRIPTIONS[error.code]
        except KeyError:
            return UNKNOWN_ERROR_DESCRIPTION

    @abstractmethod
    def ui_state(self):
        pass

    @property
    def error_level(self):
        return max((error.level for _, error in self.errors), default=BombErrorLevel.NONE)

    @abstractmethod
    def generate(self):
        pass

    @abstractmethod
    async def send_state(self):
        pass

    async def defuse(self):
        self.state = ModuleState.DEFUSED
        self._bomb.trigger(ModuleStateChange(self))
        await self._bomb.bus.send(SolveModuleMessage(self.bus_id))

    async def strike(self, count=True):
        if count:
            if await self._bomb.strike():
                return
            await self._bomb.bus.send(StrikeModuleMessage(self.bus_id))

class NeedyModule(Module): # pylint: disable=abstract-method
    is_needy = True
