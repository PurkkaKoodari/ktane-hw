from abc import ABC, abstractmethod

from ..bus import StrikeModuleMessage, ModuleId
from ..utils import Registry

MODULES = [
    "SimonSays"
]

MODULE_ID_REGISTRY = Registry("module_id")
MODULE_MESSAGE_ID_REGISTRY = Registry("message_id")

class Module(ABC):
    """
    The base class for modules.
    """

    __slots__ = "_bomb", "bus_id"

    is_needy = False
    is_boss = False

    def __init__(self, bomb, bus_id: ModuleId):
        self._bomb = bomb
        self.bus_id = bus_id

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
