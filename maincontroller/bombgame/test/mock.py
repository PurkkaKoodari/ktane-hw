from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Callable

import can

from ..bus.bus import BombBus
from ..bus.messages import ModuleId, BusMessageDirection, BusMessage, AnnounceMessage, ResetMessage
from ..gpio import AbstractGpio, ModuleReadyChange
from ..modules.base import ModuleState
from ..modules.simonsays import SimonSaysModule, SimonColor, SimonButtonPressMessage
from ..modules.timer import TimerModule
from ..utils import EventSource


def mock_bus() -> BombBus:
    can_bus = can.Bus(interface="virtual", channel="test_can_bus")
    return BombBus(can_bus)


class MockGpioEnableChange:
    def __init__(self, location: int, state: bool):
        self.location = location
        self.state = state


class MockGpio(AbstractGpio):

    def __init__(self):
        AbstractGpio.__init__(self)
        self._ready_pins = {}
        self._enable_pins = {}
        self._widget_pins = {}

    def get_enable_state(self, location: int) -> bool:
        return self._enable_pins.get(location, False)

    def get_widget_state(self, location: int) -> bool:
        return self._widget_pins.get(location, False)

    def set_ready_state(self, location: int, present: bool):
        if self._ready_pins.get(location, False) != present:
            self._ready_pins[location] = present
            self.trigger(ModuleReadyChange(location, present))

    async def reset(self) -> None:
        values = self._enable_pins.copy()
        self._enable_pins.clear()
        self._widget_pins.clear()
        for location, value in self._enable_pins.items():
            if value:
                self.trigger(MockGpioEnableChange(location, False))

    async def check_ready_changes(self) -> List[int]:
        return [location for location, present in self._ready_pins.items() if present]

    async def set_enable(self, location: int, enabled: bool) -> None:
        if self.get_enable_state(location) != enabled:
            self._enable_pins[location] = enabled
            self.trigger(MockGpioEnableChange(location, enabled))

    async def set_widget(self, location: int, value: bool) -> None:
        self._widget_pins[location] = value


class PhysicalModuleState(Enum):
    RESET = 0
    INITIALIZATION = 1
    CONFIGURATION = 2
    GAME = 3
    UNPLUGGED = -1


class MockModule(ABC, EventSource):
    def __init__(self, bus: BombBus, gpio: MockGpio, location: int, module_id: ModuleId):
        EventSource.__init__(self)
        self._bus = bus
        self._gpio = gpio
        self.location = location
        self.module_id = module_id
        self.state = PhysicalModuleState.UNPLUGGED
        self._reset_state()
        gpio.add_listener(MockGpioEnableChange, self._handle_enable_change)
        bus.add_listener(BusMessage, self._handle_message)

    def plug(self):
        if self.state != PhysicalModuleState.UNPLUGGED:
            raise RuntimeError("module already plugged in")
        self._soft_reset()

    def unplug(self):
        if self.state == PhysicalModuleState.UNPLUGGED:
            raise RuntimeError("module not plugged in")
        self.state = PhysicalModuleState.UNPLUGGED
        self._reset_state()
        self._gpio.set_ready_state(self.location, False)

    def _handle_enable_change(self, event: MockGpioEnableChange):
        if self.state == PhysicalModuleState.UNPLUGGED:
            return
        if event.location == self.location and event.state and self.state == PhysicalModuleState.RESET:
            self._enter_init()

    def _soft_reset(self):
        self.state = PhysicalModuleState.RESET
        self._reset_state()
        if self._gpio.get_enable_state(self.location):
            self._enter_init()
        else:
            self._gpio.set_ready_state(self.location, True)

    def _enter_init(self):
        self._gpio.set_ready_state(self.location, False)
        self._announce()
        self.state = PhysicalModuleState.INITIALIZATION

    @abstractmethod
    def _reset_state(self):
        pass

    @abstractmethod
    def _announce(self):
        pass

    def _handle_message(self, message: BusMessage):
        if isinstance(message, ResetMessage):
            self._soft_reset()
            return
        if self.state == ModuleState.RESET:
            return
        # TODO handle more messages


class MockTimerModule(MockModule):
    displayed_time: float
    speed: float

    def __init__(self, bus: BombBus, gpio: MockGpio, location: int, serial: int = 0):
        MockModule.__init__(self, bus, gpio, location, ModuleId(TimerModule.module_id, serial))

    def _reset_state(self):
        self.displayed_time = 0.0
        self.speed = 0.0

    async def _announce(self):
        await self._bus.send(AnnounceMessage(self.module_id, BusMessageDirection.IN, hw_version=(1, 0), sw_version=(1, 0), init_complete=True))


class MockSimonModule(MockModule):
    blinks: list

    def __init__(self, bus: BombBus, gpio: MockGpio, location: int, serial: int = 0):
        MockModule.__init__(self, bus, gpio, location, ModuleId(SimonSaysModule.module_id, serial))

    def _reset_state(self):
        self.blinks = []

    async def press_button(self, color: SimonColor):
        await self._bus.send(SimonButtonPressMessage(self.module_id, BusMessageDirection.IN, color=color))

    async def _announce(self):
        await self._bus.send(AnnounceMessage(self.module_id, BusMessageDirection.IN, hw_version=(1, 0), sw_version=(1, 0), init_complete=True))
