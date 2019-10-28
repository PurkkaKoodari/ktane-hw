from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum
from threading import RLock

from ..bus.messages import StrikeModuleMessage, ModuleId

class ModuleState(Enum):
    RESET = 0
    INITIALIZATION = 1
    CONFIGURATION = 2

class Module(ABC):
    """
    The base class for modules.
    """

    __slots__ = ("_bomb", "bus_id", "location", "_state", "_state_lock")

    is_needy = False
    is_boss = False

    def __init__(self, bomb, bus_id: ModuleId):
        self._bomb = bomb
        self.bus_id = bus_id
        self.location = None
        self._state = ModuleState.RESET
        self._state_lock = RLock()

    @property
    def state(self):
        return self._state

    @state.setter
    def _set_state(self, state):
        with self._state_lock:
            self._state = state

    @abstractmethod
    def generate(self):
        pass

    def strike(self, count=True):
        if count:
            if self._bomb.strike():
                return
            self._bomb.send(StrikeModuleMessage(self.bus_id))

class NeedyModule(Module): # pylint: disable=abstract-method
    is_needy = True
