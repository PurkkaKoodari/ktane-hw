from abc import ABC, abstractmethod
from collections import namedtuple
from typing import Iterable

MCP23017Spec = namedtuple("MCP23017Spec", ["mcp23017_addr", "ready_pins", "enable_pins", "widget_pins"])


class Casing(ABC):
    """The base class for the bomb casings."""

    @property
    @abstractmethod
    def capacity(self) -> int:
        """The number of modules that fit in this casing."""

    @property
    @abstractmethod
    def widget_capacity(self) -> int:
        """The number of widgets that fit in this casing."""

    @abstractmethod
    def location(self, index: int) -> str:
        """Returns a textual representation of a location.

        Only used in the UI. Will only be called with ``0 <= index < capacity``.
        """

    @property
    @abstractmethod
    def gpio_config(self) -> Iterable[MCP23017Spec]:
        """An iterable of MCP23017Spec objects that specify the I2C addresses and pins used for MCP23017 IO expanders
        for the module ready, module enable and widget pins.

        Modules and widgets are specified such that the ``location`` indexing starts with location 0 as the first pins
        specified in the first MCP23017 and continues cumulatively through the MCP23017s.
        """


class VanillaCasing(Casing):
    """The bomb casing in the vanilla game."""

    capacity = 4
    widget_capacity = 0

    def location(self, index: int) -> str:
        if not 0 <= index < 12:
            raise ValueError("index must be between 0 and 11")
        return f"{'front' if index < 6 else f'back'} side, row {index // 3 % 2 + 1}, column {index % 3 + 1}"

    # TODO add all expanders for full setup
    gpio_config = (
        MCP23017Spec(0x20, (0, 1, 2, 3), (4, 5, 6, 7), ()),
        # MCP23017Spec(0x21, (0, 1), (4, 5), ()),
        # MCP23017Spec(0x22, (0, 1), (4, 5), ()),
        # MCP23017Spec(0x23, (0, 1), (4, 5), ()),
        # MCP23017Spec(0x24, (0, 1), (4, 5), ()),
        # MCP23017Spec(0x25, (0, 1), (4, 5), ())
    )
