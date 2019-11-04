from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum
from threading import RLock
from typing import Tuple

from ..bus.messages import StrikeModuleMessage, SolveModuleMessage, ModuleId

class ModuleState(Enum):
    INITIALIZATION = 1
    CONFIGURATION = 2

class Module(ABC):
    """
    The base class for modules.
    """

    __slots__ = ("_bomb", "bus_id", "location", "hw_version", "sw_version", "ping_time", "_state", "_state_lock")

    is_needy = False
    is_boss = False

    def __init__(self, bomb, bus_id: ModuleId, location: int, hw_version: Tuple[int], sw_version: Tuple[int]):
        self._bomb = bomb
        self.bus_id = bus_id
        self.location = location
        self.hw_version = hw_version
        self.sw_version = sw_version
        self.ping_time = None
        self._state = ModuleState.INITIALIZATION
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

    @abstractmethod
    def prepare(self):
        pass

    def solve(self):
        self._bomb.send(SolveModuleMessage(self.bus_id))

    def strike(self, count=True):
        if count:
            if self._bomb.strike():
                return
            self._bomb.bus.send(StrikeModuleMessage(self.bus_id))

class NeedyModule(Module): # pylint: disable=abstract-method
    is_needy = True
