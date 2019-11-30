from abc import ABC, abstractmethod, abstractproperty
from collections import namedtuple
from typing import Iterable

MCP23017Spec = namedtuple("MCP23017Pins", ["mcp23017_addr", "ready_pins", "enable_pins", "widget_pins"])

class Casing(ABC):
    """
    The base class for the bomb casings.
    """

    @abstractproperty
    def capacity(self) -> int:
        pass

    @abstractproperty
    def widget_capacity(self) -> int:
        pass

    @abstractmethod
    def location(self, index: int) -> str:
        pass

    @abstractproperty
    def gpio_config(self) -> Iterable[MCP23017Spec]:
        pass

class VanillaCasing(Casing):
    """
    The bomb casing in the vanilla game.
    """

    capacity = 0
    widget_capacity = 0

    def location(self, index: int) -> str:
        if not 0 <= index < 12:
            raise ValueError("index must be between 0 and 11")
        return f"{'front' if index < 6 else f'back'} side, row {index // 3 % 2 + 1}, column {index % 3}"

    # TODO get real values
    gpio_config = (
        MCP23017Spec(0x20, (0, 1), (2, 3), ()),
        # MCP23017Spec(0x21, (0, 1), (2, 3), ()),
        # MCP23017Spec(0x22, (0, 1), (2, 3), ()),
        # MCP23017Spec(0x23, (0, 1), (2, 3), ()),
        # MCP23017Spec(0x24, (0, 1), (2, 3), ()),
        # MCP23017Spec(0x25, (0, 1), (2, 3), ())
    )
