from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum
from threading import RLock
from time import monotonic
from typing import Tuple

from ..bus.messages import StrikeModuleMessage, SolveModuleMessage, ModuleId

class ModuleState(Enum):
    INITIALIZATION = 1
    CONFIGURATION = 2

class Module(ABC):
    """
    The base class for modules.
    """

    __slots__ = ("_bomb", "bus_id", "location", "hw_version", "sw_version", "last_received", "last_ping_sent", "state")

    is_needy = False
    is_boss = False

    def __init__(self, bomb, bus_id: ModuleId, location: int, hw_version: Tuple[int], sw_version: Tuple[int]):
        self._bomb = bomb
        self.bus_id = bus_id
        self.location = location
        self.hw_version = hw_version
        self.sw_version = sw_version
        self.last_received = self.last_ping_sent = monotonic()
        self.state = ModuleState.INITIALIZATION

    @abstractmethod
    def generate(self):
        pass

    @abstractmethod
    async def prepare(self):
        pass

    async def solve(self):
        await self._bomb.bus.send(SolveModuleMessage(self.bus_id))

    async def strike(self, count=True):
        if count:
            if await self._bomb.strike():
                return
            await self._bomb.bus.send(StrikeModuleMessage(self.bus_id))

class NeedyModule(Module): # pylint: disable=abstract-method
    is_needy = True
