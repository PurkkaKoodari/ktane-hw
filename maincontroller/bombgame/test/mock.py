from abc import ABC, abstractmethod
from asyncio import create_task
from enum import Enum
from typing import List, Tuple

import can

from bombgame.bus.bus import BombBus
from bombgame.bus.messages import (ModuleId, BusMessageDirection, BusMessage, AnnounceMessage, ResetMessage,
                                   InitCompleteMessage, PingMessage, LaunchGameMessage, StartTimerMessage,
                                   ExplodeBombMessage, DefuseBombMessage, StrikeModuleMessage, SolveModuleMessage,
                                   NeedyActivateMessage, NeedyDeactivateMessage)
from bombgame.gpio import AbstractGpio, ModuleReadyChange
from bombgame.modules.registry import MODULE_ID_REGISTRY
from bombgame.modules.simonsays import SimonSaysModule, SimonColor, SimonButtonPressMessage, SimonButtonBlinkMessage
from bombgame.modules.timer import TimerModule, SetTimerStateMessage
from bombgame.utils import EventSource, VersionNumber


def mock_can_bus() -> can.BusABC:
    return can.Bus(interface="virtual", channel="test_can_bus")


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
        """Gets the state of a virtual enable pin. Called by testing code."""
        return self._enable_pins.get(location, False)

    def get_widget_state(self, location: int) -> bool:
        """Gets the state of a virtual widget pin. Called by testing code."""
        return self._widget_pins.get(location, False)

    def set_ready_state(self, location: int, present: bool):
        """Sets the state of a virtual ready pin. Called by testing code."""
        if self._ready_pins.get(location, False) != present:
            self._ready_pins[location] = present
            self.trigger(ModuleReadyChange(location, present))

    async def reset(self) -> None:
        values = self._enable_pins.copy()
        self._enable_pins.clear()
        self._widget_pins.clear()
        for location, enabled in values.items():
            if enabled:
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
    CRASHED = -2


class MockPhysicalModule(ABC, EventSource):
    def __init__(self, bus: BombBus, gpio: MockGpio, location: int, module_id: ModuleId):
        EventSource.__init__(self)
        self._bus = bus
        self._gpio = gpio
        self.location = location
        self.module_id = module_id
        self.state = PhysicalModuleState.UNPLUGGED
        self.solved = False
        self.strikes = 0
        self._reset_state()
        gpio.add_listener(MockGpioEnableChange, self._handle_enable_change)
        bus.add_listener(BusMessage, self._handle_message)

    def unplug(self):
        self.state = PhysicalModuleState.UNPLUGGED
        self._reset_state()
        self._gpio.set_ready_state(self.location, False)

    def crash(self):
        self.state = PhysicalModuleState.CRASHED

    async def _handle_enable_change(self, event: MockGpioEnableChange):
        if self.state in (PhysicalModuleState.UNPLUGGED, PhysicalModuleState.CRASHED):
            return
        if event.location == self.location and event.state and self.state == PhysicalModuleState.RESET:
            await self._enter_init()

    def hard_reset(self):
        self.state = PhysicalModuleState.RESET
        self._reset_state()
        if self._gpio.get_enable_state(self.location):
            create_task(self._enter_init())
        else:
            self._gpio.set_ready_state(self.location, True)

    async def _enter_init(self):
        self._gpio.set_ready_state(self.location, False)
        self.state = PhysicalModuleState.INITIALIZATION
        hw_version, sw_version, init_complete = self._announce()
        await self._bus.send(AnnounceMessage(self.module_id, BusMessageDirection.IN, hw_version=hw_version, sw_version=sw_version, init_complete=init_complete))
        if init_complete:
            self.state = PhysicalModuleState.CONFIGURATION

    async def _init_complete(self):
        await self._bus.send(InitCompleteMessage(self.module_id, BusMessageDirection.IN))
        self.state = PhysicalModuleState.CONFIGURATION

    @abstractmethod
    def _reset_state(self):
        pass

    @abstractmethod
    def _announce(self) -> Tuple[VersionNumber, VersionNumber, bool]:
        pass

    async def _handle_message(self, message: BusMessage):
        if self.state in (PhysicalModuleState.UNPLUGGED, PhysicalModuleState.CRASHED):
            return
        if message.module != ModuleId.BROADCAST and message.module != self.module_id:
            return
        if isinstance(message, ResetMessage):
            self.hard_reset()
            return
        if self.state == PhysicalModuleState.RESET:
            return
        if isinstance(message, PingMessage):
            await self._bus.send(PingMessage(self.module_id, BusMessageDirection.IN, number=message.number))
            return
        default_handled = False
        if isinstance(message, LaunchGameMessage):
            self.state = PhysicalModuleState.GAME
            default_handled = True
        if isinstance(message, StrikeModuleMessage):
            self.strikes += 1
            default_handled = True
        if isinstance(message, SolveModuleMessage):
            self.solved = True
            default_handled = True
        if isinstance(message, (StartTimerMessage, ExplodeBombMessage, DefuseBombMessage)):
            default_handled = True
        if isinstance(message, (NeedyActivateMessage, NeedyDeactivateMessage)) and self._module_class().is_needy:
            default_handled = True
        if await self._handle_module_message(message):
            return
        if not default_handled:
            raise AssertionError(f"{self.module_id} got unexpected {message.__class__.__name__}")

    @abstractmethod
    async def _handle_module_message(self, message: BusMessage) -> bool:
        pass

    def _module_class(self):
        return MODULE_ID_REGISTRY[self.module_id.type]


class MockPhysicalTimer(MockPhysicalModule):
    displayed_time: float
    speed: float

    def __init__(self, bus: BombBus, gpio: MockGpio, location: int, serial: int = 0):
        MockPhysicalModule.__init__(self, bus, gpio, location, ModuleId(TimerModule.module_id, serial))

    def _reset_state(self):
        self.displayed_time = 0.0
        self.speed = 0.0

    def _announce(self):
        return VersionNumber(1, 0), VersionNumber(1, 0), True

    async def _handle_module_message(self, message: BusMessage) -> bool:
        if isinstance(message, SetTimerStateMessage):
            self.displayed_time = message.secs
            self.speed = message.speed
            return True
        return False


class MockPhysicalSimon(MockPhysicalModule):
    blinks: list

    def __init__(self, bus: BombBus, gpio: MockGpio, location: int, serial: int = 0):
        MockPhysicalModule.__init__(self, bus, gpio, location, ModuleId(SimonSaysModule.module_id, serial))

    def _reset_state(self):
        self.blinks = []

    async def press_button(self, color: SimonColor):
        await self._bus.send(SimonButtonPressMessage(self.module_id, BusMessageDirection.IN, color=color))

    def _announce(self):
        return VersionNumber(1, 0), VersionNumber(1, 0), True

    async def _handle_module_message(self, message: BusMessage) -> bool:
        if isinstance(message, SimonButtonBlinkMessage):
            self.blinks.append(message.color)
            return True
        return False
