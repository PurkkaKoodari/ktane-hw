from abc import ABC, abstractmethod

from .bus import BombBus, DefuseBombMessage, ExplodeBombMessage, ModuleId
from .modules import Module
from .utils import EventSource

class Casing(ABC):
    """
    The base class for the bomb casings.
    """

    @abstractmethod
    def capacity(self) -> int:
        pass

    @abstractmethod
    def location(self, index: int) -> str:
        pass

class VanillaCasing(Casing):
    """
    The bomb casing in the vanilla game.
    """

    def capacity(self) -> int:
        return 12

    def location(self, index: int) -> str:
        if not 0 <= index < 12:
            raise ValueError("index must be between 0 and 11")
        return f"{'front' if index < 6 else f'back'} side, row {index // 3 % 2 + 1}, column {index % 3}"

class Bomb(EventSource):
    """
    The bomb, consisting of a casing and modules.
    """

    DEFAULT_MAX_STRIKES = 3

    def __init__(self, bus: BombBus, *, max_strikes=DEFAULT_MAX_STRIKES, casing=None):
        self._bus = bus
        self.casing = casing or VanillaCasing()
        self.modules = []
        self.max_strikes = max_strikes
        self.strikes = 0

    def add_module(self, module: Module):
        self.modules.append(module)

    def explode(self):
        self._bus.send(ExplodeBombMessage(ModuleId.BROADCAST))

    def defuse(self):
        self._bus.send(DefuseBombMessage(ModuleId.BROADCAST))

    def strike(self) -> bool:
        self.strikes += 1
        if self.strikes >= self.max_strikes:
            self.explode()
            return True
        return False
