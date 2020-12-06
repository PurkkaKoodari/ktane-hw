from abc import ABC, abstractmethod
from enum import Enum
from random import choice, randrange
from typing import Optional, Tuple, List

from bombgame.bomb.serial import BombSerial


class BatteryType(Enum):
    AA = "AA"
    D = "D"


class Widget(ABC):
    @abstractmethod
    def serialize(self) -> dict:
        """Serializes the widget to JSON."""


class BatteryHolder(Widget):
    def __init__(self, type_: BatteryType):
        self.type = type_
        self.batteries = 2 if type_ == "AA" else 1

    def serialize(self):
        return {
            "type": "battery",
            "battery_type": self.type.name,
        }


class PortType(Enum):
    PARALLEL = "parallel"
    SERIAL = "serial"
    RJ45 = "rj45"
    RCA = "rca"
    DVI = "dvi"
    PS2 = "ps2"


class PortPlate(Widget):
    def __init__(self, ports: Tuple[PortType, ...]):
        self.ports = ports

    def serialize(self):
        return {
            "type": "port_plate",
            "ports": [port.name for port in self.ports],
        }


class IndicatorName(Enum):
    SND = "SND"
    CLR = "CLR"
    CAR = "CAR"
    IND = "IND"
    FRQ = "FRQ"
    SIG = "SIG"
    NSA = "NSA"
    MSA = "MSA"
    TRN = "TRN"
    BOB = "BOB"
    FRK = "FRK"


class Indicator(Widget):
    def __init__(self, name: IndicatorName, state: Optional[bool]):
        self.name = name
        self.state = state

    @property
    def lit(self):
        return self.state is True

    @property
    def unlit(self):
        return self.state is False

    @property
    def present(self):
        return self.state is not None

    def __bool__(self):
        return self.present

    def serialize(self):
        return {
            "type": "port_plate",
            "name": self.name.name,
            "lit": self.lit,
        }


class Edgework:
    serial_number: BombSerial
    widgets: List[Widget]

    def __init__(self):
        # TODO: widget/edgework configuration from web ui
        self.serial_number = BombSerial.generate()
        self.widgets = []
        widget_count = 5
        unused_indicators = list(IndicatorName.__members__.values())
        for _ in range(widget_count):
            widget_type = randrange(3)
            if widget_type == 0:
                # generate indicator
                indicator_name = choice(unused_indicators)
                unused_indicators.remove(indicator_name)
                lit = randrange(2) == 1
                widget = Indicator(indicator_name, lit)
            elif widget_type == 1:
                # generate port plate
                plate_type = randrange(2)
                port_types = (PortType.PARALLEL, PortType.SERIAL) if plate_type == 0 else (PortType.RJ45, PortType.RCA, PortType.DVI, PortType.PS2)
                port_types = tuple(port for port in port_types if randrange(2) == 1)
                widget = PortPlate(port_types)
            else:
                # generate batteries
                battery_type = choice((BatteryType.AA, BatteryType.D))
                widget = BatteryHolder(battery_type)
            self.widgets.append(widget)

    def batteries(self, type_: Optional[BatteryType] = None):
        return sum(widget.batteries for widget in self.widgets
                   if isinstance(widget, BatteryHolder) and type_ in (None, widget.type))

    @property
    def battery_holders(self) -> int:
        return sum(isinstance(widget, BatteryHolder) for widget in self.widgets)

    @property
    def indicators(self) -> List[Indicator]:
        return [widget for widget in self.widgets if isinstance(widget, Indicator)]

    def indicator(self, name: IndicatorName) -> Indicator:
        for widget in self.indicators:
            if widget.name == name:
                return widget
        return Indicator(name, None)

    def ports(self, type_: Optional[PortType] = None):
        return sum(port == type_ for widget in self.port_plates for port in widget.ports)

    @property
    def port_plates(self) -> List[PortPlate]:
        return [widget for widget in self.widgets if isinstance(widget, PortPlate)]

    def serialize(self) -> Tuple[str, list]:
        return self.serial_number, [widget.serialize() for widget in self.widgets]
