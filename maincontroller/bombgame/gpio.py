from __future__ import annotations

from abc import ABC, abstractmethod
from asyncio import Lock, create_task, sleep as async_sleep, get_running_loop, Task
from collections import namedtuple
from logging import getLogger
from typing import List, Optional

from bombgame import mcp23017
from bombgame.casings import Casing
from bombgame.config import GPIO_SMBUS_ADDR, GPIO_POLL_INTERVAL, GPIO_INTERRUPT_ENABLED, GPIO_INTERRUPT_PIN
from bombgame.utils import AuxiliaryThreadExecutor, EventSource, log_errors

LOGGER = getLogger("GPIO")


class ModuleReadyChange:
    """The event that is raised when a module is added or removed."""

    __slots__ = ("location", "present")

    def __init__(self, location: int, present: bool):
        self.location = location
        self.present = present

    def __repr__(self):
        status = "present" if self.present else "not present"
        return f"<ModuleReadyChange: location {self.location} is now {status}>"


class AbstractGpio(EventSource, ABC):
    """An abstract base class for Gpio and MockGpio."""

    def __init__(self):
        EventSource.__init__(self)

    @abstractmethod
    async def reset(self) -> None:
        """Resets all module enable and widget pins to off."""

    @abstractmethod
    async def check_ready_changes(self) -> List[int]:
        """Polls for changes in module ready pins and returns the locations of currently connected modules."""

    @abstractmethod
    async def set_enable(self, location: int, enabled: bool) -> None:
        """Sets the state of the MODULE_ENABLE signal for a module."""

    @abstractmethod
    async def set_widget(self, location: int, value: bool) -> None:
        """Sets the state of a widget pin."""


_ModuleInfo = namedtuple("_ModuleInfo", ["mcp", "ready", "enable"])
_WidgetInfo = namedtuple("_WidgetInfo", ["mcp", "widget"])


class Gpio(AbstractGpio):
    """A class that manages all the MCP23017 chips in a Casing.

    All public methods are asynchronous.
    """

    _mcps: List[mcp23017.MCP23017]
    _modules: List[_ModuleInfo]
    _widgets: List[_WidgetInfo]
    _prev_ready: List[bool]
    _lock: Lock
    _poller: Optional[Task]
    _executor: AuxiliaryThreadExecutor

    def __init__(self, casing: Casing):
        """Creates a Gpio object and synchronously initializes the MCP23017 chips."""
        AbstractGpio.__init__(self)
        LOGGER.info("Initializing GPIO for %s", casing.__class__.__name__)
        self._mcps = []
        self._modules = []
        self._widgets = []
        self._prev_ready = [False] * casing.capacity
        self._lock = Lock()
        self._poller = None
        self._executor = AuxiliaryThreadExecutor(name="GPIO")
        self._initialize_mcps(casing)
        self._initialize_interrupt()
        assert len(self._modules) == casing.capacity
        assert len(self._widgets) == casing.widget_capacity

    def _initialize_mcps(self, casing: Casing):
        for spec in casing.gpio_config:
            assert len(spec.ready_pins) == len(spec.enable_pins)
            LOGGER.debug("Initializing MCP23017 at SMBus %s address %#x", GPIO_SMBUS_ADDR, spec.mcp23017_addr)
            mcp = mcp23017.MCP23017(GPIO_SMBUS_ADDR, spec.mcp23017_addr)
            with mcp.begin_configuration():
                mcp.configure_int_pins(mirror=True)
                for ready, enable in zip(spec.ready_pins, spec.enable_pins):
                    mcp.pin_mode(None, ready, mcp23017.INPUT_PULLUP, invert=True)
                    mcp.pin_interrupt(None, ready, mcp23017.BOTH if GPIO_INTERRUPT_ENABLED else mcp23017.OFF)
                    mcp.pin_mode(None, enable, mcp23017.OUTPUT, invert=True)
                    mcp.write_pin(None, enable, False)
                    self._modules.append(_ModuleInfo(mcp, ready, enable))
                for widget in spec.widget_pins:
                    mcp.pin_mode(None, widget, mcp23017.OUTPUT)
                    mcp.write_pin(None, widget, False)
                    self._widgets.append(_WidgetInfo(mcp, widget))
            self._mcps.append(mcp)

    def _initialize_interrupt(self):
        # pylint: disable=no-member
        try:
            import RPi.GPIO as GPIO
        except (ImportError, RuntimeError):
            LOGGER.warning("Failed to load RPi.GPIO module. Module ready interrupts will be disabled.")
            return
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(GPIO_INTERRUPT_PIN, GPIO.IN)
        GPIO.add_event_detect(GPIO_INTERRUPT_PIN, GPIO.FALLING, self.check_ready_changes)

    def start(self):
        """Starts the GPIO auxiliary thread and module ready polling."""
        if self._poller is not None:
            raise RuntimeError("polling already started")
        LOGGER.info("Starting GPIO poller")
        self._executor.start()
        self._poller = create_task(log_errors(self._poll_gpio_loop()))

    def stop(self):
        """Stops the GPIO auxiliary thread and module ready polling."""
        if self._poller is None:
            raise RuntimeError("polling not started")
        LOGGER.info("Stopping GPIO poller")
        self._poller.cancel()
        self._executor.shutdown(True)

    async def _poll_gpio_loop(self):
        while True:
            await self.check_ready_changes()
            await async_sleep(GPIO_POLL_INTERVAL)

    async def reset(self):
        """Resets all module enable and widget pins to off."""
        async with self._lock:
            await get_running_loop().run_in_executor(self._executor, self._sync_reset)

    def _sync_reset(self):
        for mcp in self._mcps:
            mcp.begin_write()
        for module in self._modules:
            module.mcp.write_pin(None, module.enable, False)
        for widget in self._widgets:
            widget.mcp.write_pin(None, widget.widget, False)
        for mcp in self._mcps:
            mcp.end_write()

    async def check_ready_changes(self):
        """Polls for changes in module ready pins and returns the locations of currently connected modules."""
        async with self._lock:
            await get_running_loop().run_in_executor(self._executor, self._sync_check_ready_changes)
        return [location for location in range(len(self._modules)) if self._prev_ready[location]]

    def _sync_check_ready_changes(self):
        for mcp in self._mcps:
            mcp.begin_read()
        for location, module in enumerate(self._modules):
            current = module.mcp.read_pin(None, module.ready)
            if current != self._prev_ready[location]:
                self.trigger(ModuleReadyChange(location, current))
            self._prev_ready[location] = current
        for mcp in self._mcps:
            mcp.end_read()

    async def set_enable(self, location: int, enabled: bool):
        """Sets the state of a single module enable pin."""
        if not 0 <= location < len(self._modules):
            raise ValueError("module location out of range")
        async with self._lock:
            await get_running_loop().run_in_executor(self._executor, self._sync_set_enable, location, enabled)

    def _sync_set_enable(self, location: int, enabled: bool):
        module = self._modules[location]
        module.mcp.write_pin(None, module.enable, enabled)

    async def set_widget(self, location: int, value: bool):
        """Sets the state of a single widget pin."""
        if not 0 <= location <= len(self._widgets):
            raise ValueError("widget location out of range")
        async with self._lock:
            await get_running_loop().run_in_executor(self._executor, self._sync_set_widget, location, value)

    def _sync_set_widget(self, location: int, value: bool):
        widget = self._widgets[location]
        widget.mcp.write_pin(None, widget.widget, value)
