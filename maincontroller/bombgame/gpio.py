from __future__ import annotations
from collections import namedtuple
from logging import getLogger
from asyncio import Lock, create_task, sleep as async_sleep, wrap_future

from smbus import SMBus

from .casings import Casing
from .utils import AuxiliaryThreadExecutor, EventSource

def _validate_port_pin(port: MCP23017.Port, pin: int):
    if port is None:
        port, pin = (MCP23017.B, pin - 8) if pin >= 8 else (MCP23017.A, pin)
    if not 0 <= pin <= 7:
        raise ValueError("pin must be between 0 and 15")
    return port, pin

class MCP23017:
    Port = namedtuple("Port", ["number", "IODIRx", "IPOLx", "GPINTENx", "DEFVALx", "INTCONx", "GPPUx", "INTFx", "INTCAPx", "GPIOx", "OLATx"])
    IntMode = namedtuple("IntMode", ["GPINTENx", "DEFVALx", "INTCONx"])
    PinMode = namedtuple("PinMode", ["IODIRx", "GPPUx"])
    Interrupt = namedtuple("Interrupt", ["port", "pin", "cont_pin", "captured"])

    IODIRA = 0x00
    IODIRB = 0x10
    IPOLA = 0x01
    IPOLB = 0x11
    GPINTENA = 0x02
    GPINTENB = 0x12
    DEFVALA = 0x03
    DEFVALB = 0x13
    INTCONA = 0x04
    INTCONB = 0x14
    IOCON = 0x05
    GPPUA = 0x06
    GPPUB = 0x16
    INTFA = 0x07
    INTFB = 0x17
    INTCAPA = 0x08
    INTCAPB = 0x18
    GPIOA = 0x09
    GPIOB = 0x19
    OLATA = 0x0A
    OLATB = 0x1A

    IOCON_BANK = 0x80
    IOCON_MIRROR = 0x40
    IOCON_SEQOP = 0x20
    IOCON_DISSLW = 0x10
    IOCON_HAEN = 0x08
    IOCON_ODR = 0x04
    IOCON_INTPOL = 0x02

    A = Port(0, IODIRA, IPOLA, GPINTENA, DEFVALA, INTCONA, GPPUA, INTFA, INTCAPA, GPIOA, OLATA)
    B = Port(1, IODIRB, IPOLB, GPINTENB, DEFVALB, INTCONB, GPPUB, INTFB, INTCAPB, GPIOB, OLATB)

    INPUT = PinMode(1, 0)
    INPUT_PULLUP = PinMode(1, 1)
    OUTPUT = PinMode(0, 0)

    RISING = IntMode(1, 0, 1)
    FALLING = IntMode(1, 1, 1)
    BOTH = IntMode(1, 0, 0)
    OFF = IntMode(0, 0, 0)

    def __init__(self, smbus_addr, i2c_addr):
        self._addr = i2c_addr
        self._bus = SMBus(smbus_addr)
        self._outputs = [0x00, 0x00]
        self._dirs = [0xff, 0xff]
        self._invs = [0x00, 0x00]
        self._pulls = [0x00, 0x00]
        self._inten = [0x00, 0x00]
        self._defval = [0x00, 0x00]
        self._intcon = [0x00, 0x00]
        self._iocon = 0x00
        self._configuring = False
        self._reads = None
        self._writes = None

    def read_port(self, port: Port):
        return self._bus.read_byte_data(self._addr, port.GPIOx)

    def read_port_interrupt(self, port: Port):
        return self._bus.read_byte_data(self._addr, port.INTFx)

    def read_port_interrupt_captured(self, port: Port):
        return self._bus.read_byte_data(self._addr, port.INTCAPx)

    def write_port(self, port: Port, byte: int):
        self._outputs[port.number] = byte
        if not self._configuring:
            self._bus.write_byte_data(self._addr, port.GPIOx, byte)

    def set_port_direction(self, port: Port, dirs: int):
        self._dirs[port.number] = dirs
        if not self._configuring:
            self._bus.write_byte_data(self._addr, port.IODIRx, dirs)

    def set_port_invert(self, port: Port, invs: int):
        self._invs[port.number] = invs
        if not self._configuring:
            self._bus.write_byte_data(self._addr, port.IPOLx, invs)

    def set_port_pullup(self, port: Port, pulls: int):
        self._pulls[port.number] = pulls
        if not self._configuring:
            self._bus.write_byte_data(self._addr, port.GPPUx, pulls)

    def set_port_interrupt(self, port: Port, enable: int, defval: int = 0x00, control: int = 0x00):
        self._inten[port.number] = enable
        self._defval[port.number] = defval
        self._intcon[port.number] = control
        if not self._configuring:
            self._bus.write_byte_data(self._addr, port.GPINTENx, enable)
            self._bus.write_byte_data(self._addr, port.DEFVALx, defval)
            self._bus.write_byte_data(self._addr, port.INTCONx, control)

    def set_io_configuration(self, iocon: int):
        self._iocon = iocon
        if not self._configuring:
            self._bus.write_byte_data(self._addr, MCP23017.IOCON, iocon)

    def read_pin(self, port: Port, pin: int):
        port, pin = _validate_port_pin(port, pin)
        if self._reads is not None:
            if self._reads[port.number] is None:
                self._reads[port.number] = self.read_port(port)
            return (self._reads[port.number] >> pin) & 1
        port_byte = self.read_port(port)
        return bool((port_byte >> pin) & 1)

    def write_pin(self, port: Port, pin: int, value: bool):
        port, pin = _validate_port_pin(port, pin)
        if self._writes is not None:
            new_val = (self._writes[port.number] & ~(1 << pin)) | (1 << pin if value else 0)
            self._writes[port.number] = new_val
            return
        new_val = (self._outputs[port.number] & ~(1 << pin)) | (1 << pin if value else 0)
        self.write_port(port, new_val)

    def pin_mode(self, port: Port, pin: int, mode: PinMode, invert: bool = False):
        port, pin = _validate_port_pin(port, pin)
        new_dirs = (self._dirs[port.number] & ~(1 << pin)) | (mode.IODIRx << pin)
        new_pulls = (self._pulls[port.number] & ~(1 << pin)) | (mode.GPPUx << pin)
        new_invs = (self._invs[port.number] & ~(1 << pin)) | (1 << pin if invert else 0)
        self.set_port_invert(port, new_invs)
        self.set_port_pullup(port, new_pulls)
        self.set_port_direction(port, new_dirs)

    def pin_interrupt(self, port: Port, pin: int, mode: IntMode):
        port, pin = _validate_port_pin(port, pin)
        new_inten = (self._inten[port.number] & ~(1 << pin)) | (mode.GPINTENx << pin)
        new_defval = (self._defval[port.number] & ~(1 << pin)) | (mode.DEFVALx << pin)
        new_intcon = (self._intcon[port.number] & ~(1 << pin)) | (mode.INTCONx << pin)
        self.set_port_interrupt(port, new_inten, new_defval, new_intcon)

    def configure_int_pins(self, mirror: bool, active_high: bool = False):
        new_iocon = ((self._iocon & ~MCP23017.IOCON_MIRROR & ~MCP23017.IOCON_INTPOL)
                     | (MCP23017.IOCON_MIRROR if mirror else 0)
                     | (MCP23017.IOCON_INTPOL if active_high else 0))
        self.set_io_configuration(new_iocon)

    def get_interrupts(self, port: Port = None):
        ports = [port] if port else [MCP23017.A, MCP23017.B]
        ints = []
        for port in ports:
            flags = self.read_port_interrupt(port)
            captures = self.read_port_interrupt_captured(port)
            for pin in range(8):
                if flags & (1 << pin):
                    ints.append(MCP23017.Interrupt(port, pin, port.number * 8 + pin, (captures >> pin) & 1))
        return ints

    def begin_read(self):
        self._reads = [None, None]
        return MCP23017._Reader(self)

    def end_read(self):
        self._reads = None

    def begin_write(self):
        self._writes = self._outputs
        return MCP23017._Writer(self)

    def end_write(self):
        for port in [MCP23017.A, MCP23017.B]:
            if self._writes[port.number] != self._outputs[port.number]:
                self.write_port(port, self._writes(port.number))
        self._writes = None

    def begin_configuration(self):
        self._configuring = True
        return MCP23017._Configurer(self)

    def end_configuration(self):
        self._configuring = False
        self.set_io_configuration(self._iocon)
        for port in [MCP23017.A, MCP23017.B]:
            self.write_port(port, self._outputs[port.number])
            self.set_port_invert(port, self._invs[port.number])
            self.set_port_pullup(port, self._pulls[port.number])
            self.set_port_direction(port, self._dirs[port.number])
            self.set_port_interrupt(port, self._inten[port.number], self._defval[port.number], self._intcon[port.number])

    class _Reader:
        def __init__(self, mcp):
            self._mcp = mcp

        def __enter__(self):
            pass

        def __exit__(self, _1, _2, _3):
            self._mcp.end_read()

    class _Writer:
        def __init__(self, mcp):
            self._mcp = mcp

        def __enter__(self):
            pass

        def __exit__(self, _1, _2, _3):
            self._mcp.end_write()

    class _Configurer:
        def __init__(self, mcp):
            self._mcp = mcp

        def __enter__(self):
            pass

        def __exit__(self, _1, _2, _3):
            self._mcp.end_configuration()

GPIO_POLL_INTERVAL = 1.0
SMBUS_ADDR = 1 # TODO: check actual address for Raspi 3
INTERRUPT_PIN = 22 # TODO: check actual pin number

class ModuleSenseChange:
    """The event that is raised when a module is added or removed."""

    __slots__ = ("location", "present")

    def __init__(self, location: int, present: bool):
        self.location = location
        self.present = present

class Gpio(EventSource):
    """A class that manages all the MCP23017 chips in a Casing.

    All public methods are asynchronous.
    """

    _ModuleInfo = namedtuple("_ModuleInfo", ["mcp", "sense", "enable"])
    _WidgetInfo = namedtuple("_WidgetInfo", ["mcp", "widget"])

    def __init__(self, casing: Casing):
        """Creates a Gpio object and synchronously initializes the MCP23017 chips."""
        super().__init__()
        getLogger("GPIO").info("Initializing GPIO for %s", casing.__class__.__name__)
        self._mcps = []
        self._modules = []
        self._widgets = []
        self._prev_sense = [False] * casing.capacity
        self._lock = Lock()
        self._poller = None
        self._executor = AuxiliaryThreadExecutor(name="GPIO")
        self._initialize_mcps(casing)
        self._initialize_interrupt()
        assert len(self._modules) == casing.capacity
        assert len(self._widgets) == casing.widget_capacity

    def _initialize_mcps(self, casing: Casing):
        for spec in casing.gpio_config:
            assert len(spec.sense_pins) == len(spec.enable_pins)
            getLogger("GPIO").debug("Initializing MCP23017 at SMBus %s address %#x", SMBUS_ADDR, spec.mcp23017_addr)
            mcp = MCP23017(SMBUS_ADDR, spec.mcp23017_addr)
            with mcp.begin_configuration():
                mcp.configure_int_pins(mirror=True)
                for sense, enable in zip(spec.sense_pins, spec.enable_pins):
                    mcp.pin_mode(None, sense, MCP23017.INPUT_PULLUP, invert=True)
                    mcp.pin_interrupt(None, sense, MCP23017.BOTH)
                    mcp.pin_mode(None, enable, MCP23017.OUTPUT)
                    mcp.write_pin(None, enable, False)
                    self._modules.append((mcp, sense, enable))
                for widget in spec.widget_pins:
                    mcp.pin_mode(None, widget, MCP23017.OUTPUT)
                    mcp.write_pin(None, widget, False)
                    self._widgets.append((mcp, widget))
            self._mcps.append(mcp)

    def _initialize_interrupt(self):
        # pylint: disable=no-member
        try:
            import RPi.GPIO as GPIO
        except RuntimeError:
            getLogger("GPIO").warning("Failed to load RPi.GPIO module. Module sense interrupts will be disabled.")
            return
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(INTERRUPT_PIN, GPIO.IN)
        GPIO.add_event_detect(INTERRUPT_PIN, GPIO.FALLING, self.check_sense_changes)

    def start(self):
        """Starts the GPIO auxiliary thread and module sense polling."""
        if self._poller is not None:
            raise RuntimeError("polling already started")
        self._executor.start()
        self._poller = create_task(self._poll_gpio_loop())

    def stop(self):
        """Stops the GPIO auxiliary thread and module sense polling."""
        if self._poller is None:
            raise RuntimeError("polling not started")
        self._poller.cancel()
        self._executor.shutdown(True)

    async def _poll_gpio_loop(self):
        while True:
            await self.check_sense_changes()
            await async_sleep(GPIO_POLL_INTERVAL)

    async def reset(self):
        """Resets all module enable and widget pins to off."""
        async with self._lock:
            await wrap_future(self._executor.submit(self._sync_reset))

    def _sync_reset(self):
        for mcp in self._mcps:
            mcp.begin_write()
        for module in self._modules:
            module.mcp.write_pin(module.enable, False)
        for widget in self._widgets:
            widget.mcp.write_pin(widget.widget, False)
        for mcp in self._mcps:
            mcp.end_write()

    async def check_sense_changes(self):
        """Polls for changes in module sense pins and returns the locations of currently connected modules."""
        async with self._lock:
            await wrap_future(self._executor.submit(self._sync_check_sense_changes))
        return [location for location in range(len(self._modules)) if self._prev_sense[location]]

    def _sync_check_sense_changes(self):
        for mcp in self._mcps:
            mcp.begin_read()
        for location, module in enumerate(self._modules):
            current = module.mcp.read_pin(module.enable)
            if current != self._prev_sense[location]:
                self.trigger(ModuleSenseChange(location, current))
            self._prev_sense[location] = current
        for mcp in self._mcps:
            mcp.end_read()

    async def set_enable(self, location: int, enabled: bool):
        """Sets the state of a single module enable pin."""
        if not 0 <= location < len(self._modules):
            raise ValueError("module location out of range")
        async with self._lock:
            await wrap_future(self._executor.submit(self._sync_set_enable, location, enabled))

    def _sync_set_enable(self, location: int, enabled: bool):
        module = self._modules[location]
        module.mcp.write_pin(module.enable, enabled)

    async def set_widget(self, location: int, value: bool):
        """Sets the state of a single widget pin."""
        if not 0 <= location <= len(self._widgets):
            raise ValueError("widget location out of range")
        async with self._lock:
            await wrap_future(self._executor.submit(self._sync_set_widget, location, value))

    def _sync_set_widget(self, location: int, value: bool):
        widget = self._widgets[location]
        widget.mcp.write_pin(widget.widget, value)
