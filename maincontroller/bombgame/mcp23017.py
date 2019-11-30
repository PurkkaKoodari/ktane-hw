from collections import namedtuple
from typing import Optional, List

from smbus import SMBus

Port = namedtuple("Port", ["number", "IODIRx", "IPOLx", "GPINTENx", "DEFVALx", "INTCONx", "GPPUx", "INTFx", "INTCAPx", "GPIOx", "OLATx"])
IntMode = namedtuple("IntMode", ["GPINTENx", "DEFVALx", "INTCONx"])
PinMode = namedtuple("PinMode", ["IODIRx", "GPPUx"])
Interrupt = namedtuple("Interrupt", ["port", "pin", "cont_pin", "captured"])

IODIRA = 0x00
IODIRB = 0x01
IPOLA = 0x02
IPOLB = 0x03
GPINTENA = 0x04
GPINTENB = 0x05
DEFVALA = 0x06
DEFVALB = 0x07
INTCONA = 0x08
INTCONB = 0x09
IOCON = 0x0A
# IOCON = 0x0B, intentionally skipped
GPPUA = 0x0C
GPPUB = 0x0D
INTFA = 0x0E
INTFB = 0x0F
INTCAPA = 0x10
INTCAPB = 0x11
GPIOA = 0x12
GPIOB = 0x13
OLATA = 0x14
OLATB = 0x15

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


def _validate_port_pin(port: Optional[Port], pin: int):
    if port is None:
        port, pin = (B, pin - 8) if pin >= 8 else (A, pin)
    if not 0 <= pin <= 7:
        raise ValueError("pin must be between 0 and 15")
    return port, pin


class MCP23017:
    """Controls a MCP23017 IO expander module.

    No methods should be considered thread-safe.

    On all methods expecting a port and a pin number, one may pass ``None`` for the port,
    which maps port A to pins 0-7 and port B to pins 8-15.
    """

    def __init__(self, smbus_addr: int, i2c_addr: int):
        """Creates a MCP23017 object."""
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

    def read_port(self, port: Port, *, ignore_transaction=False) -> int:
        """Reads the pins of the given port as a byte.

        If a read transaction is ongoing, the state of the port is cached until the
        end of the transaction.
        """
        if self._reads is not None and not ignore_transaction:
            if self._reads[port.number] is None:
                self._reads[port.number] = self.read_port(port, ignore_transaction=True)
            return self._reads[port.number]
        return self._bus.read_byte_data(self._addr, port.GPIOx)

    def read_port_interrupt(self, port: Port):
        """Reads the interrupt flags of a port as a byte.

        This method always issues a request to the chip, regardless of transactions.
        """
        return self._bus.read_byte_data(self._addr, port.INTFx)

    def read_port_interrupt_captured(self, port: Port):
        """Reads the interrupt captured values of a port as a byte.

        This method always issues a request to the chip, regardless of transactions.
        """
        return self._bus.read_byte_data(self._addr, port.INTCAPx)

    def write_port(self, port: Port, byte: int, *, ignore_transaction=False):
        """Writes the pins of the given port.

        If a write or configuration transaction is ongoing, the change is committed at the
        end of the transaction.
        """
        if self._writes is not None and not ignore_transaction:
            self._writes[port.number] = byte
        else:
            self._outputs[port.number] = byte
            self._bus.write_byte_data(self._addr, port.GPIOx, byte)

    def set_port_direction(self, port: Port, dirs: int):
        """Writes the direction of the given port.

        A set (1) bit indicates an input, an unset (0) bit indicates an output.

        If a configuration transaction is ongoing, the change is committed at the
        end of the transaction.
        """
        self._dirs[port.number] = dirs
        if not self._configuring:
            self._bus.write_byte_data(self._addr, port.IODIRx, dirs)

    def set_port_invert(self, port: Port, invs: int):
        """Writes the invert flags of the given port.

        A set (1) bit indicates an inverted input/output.

        If a configuration transaction is ongoing, the change is committed at the
        end of the transaction.
        """
        self._invs[port.number] = invs
        if not self._configuring:
            self._bus.write_byte_data(self._addr, port.IPOLx, invs)

    def set_port_pullup(self, port: Port, pulls: int):
        """Writes the pullup flags of the given port.

        A set (1) bit enables the input pull-up on the pin.

        If a configuration transaction is ongoing, the change is committed at the
        end of the transaction.
        """
        self._pulls[port.number] = pulls
        if not self._configuring:
            self._bus.write_byte_data(self._addr, port.GPPUx, pulls)

    def set_port_interrupt(self, port: Port, enable: int, defval: int = 0x00, control: int = 0x00):
        """Writes the interrupt registers of the given port.

        A set (1) bit in ``enable`` enables the interrupts for the pin.
        A set (1) bit in ``control`` indicates a rising or falling interrupt,
        an unset (0) bit indicates a change interrupt.
        A set (1) bit in ``defval`` indicates a falling interrupt,
        an unset (0) bit indicates a rising interrupt.

        If a configuration transaction is ongoing, the change is committed at the
        end of the transaction.
        """
        self._inten[port.number] = enable
        self._defval[port.number] = defval
        self._intcon[port.number] = control
        if not self._configuring:
            self._bus.write_byte_data(self._addr, port.GPINTENx, enable)
            self._bus.write_byte_data(self._addr, port.DEFVALx, defval)
            self._bus.write_byte_data(self._addr, port.INTCONx, control)

    def set_io_configuration(self, iocon: int):
        """Writes the general configuration register.

        If a configuration transaction is ongoing, the change is committed at the
        end of the transaction.
        """
        self._iocon = iocon
        if not self._configuring:
            self._bus.write_byte_data(self._addr, IOCON, iocon)

    def read_pin(self, port: Optional[Port], pin: int) -> bool:
        """Reads the state of a pin.

        If a read transaction is ongoing, the state of the port is cached until the
        end of the transaction.
        """
        port, pin = _validate_port_pin(port, pin)
        port_byte = self.read_port(port)
        return bool((port_byte >> pin) & 1)

    def write_pin(self, port: Optional[Port], pin: int, value: bool):
        """Writes a pin.

        If a write or configuration transaction is ongoing, the change is committed at the
        end of the transaction.
        """
        port, pin = _validate_port_pin(port, pin)
        old_val = self._writes[port.number] if self._writes is not None else self._outputs[port.number]
        new_val = (old_val & ~(1 << pin)) | (1 << pin if value else 0)
        self.write_port(port, new_val)

    def pin_mode(self, port: Optional[Port], pin: int, mode: PinMode, invert: bool = False):
        """Configures the mode of a pin.

        If a configuration transaction is ongoing, the change is committed at the
        end of the transaction.
        """
        port, pin = _validate_port_pin(port, pin)
        new_dirs = (self._dirs[port.number] & ~(1 << pin)) | (mode.IODIRx << pin)
        new_pulls = (self._pulls[port.number] & ~(1 << pin)) | (mode.GPPUx << pin)
        new_invs = (self._invs[port.number] & ~(1 << pin)) | (1 << pin if invert else 0)
        self.set_port_invert(port, new_invs)
        self.set_port_pullup(port, new_pulls)
        self.set_port_direction(port, new_dirs)

    def pin_interrupt(self, port: Optional[Port], pin: int, mode: IntMode):
        """Configures the interrupt mode on a pin.

        If a configuration transaction is ongoing, the change is committed at the
        end of the transaction.
        """
        port, pin = _validate_port_pin(port, pin)
        new_inten = (self._inten[port.number] & ~(1 << pin)) | (mode.GPINTENx << pin)
        new_defval = (self._defval[port.number] & ~(1 << pin)) | (mode.DEFVALx << pin)
        new_intcon = (self._intcon[port.number] & ~(1 << pin)) | (mode.INTCONx << pin)
        self.set_port_interrupt(port, new_inten, new_defval, new_intcon)

    def configure_int_pins(self, mirror: bool, active_high: bool = False):
        """Configures the mirroring and active level of the interrupt pins.

        If a configuration transaction is ongoing, the change is committed at the
        end of the transaction.
        """
        new_iocon = ((self._iocon & ~IOCON_MIRROR & ~IOCON_INTPOL)
                     | (IOCON_MIRROR if mirror else 0)
                     | (IOCON_INTPOL if active_high else 0))
        self.set_io_configuration(new_iocon)

    def get_interrupts(self, port: Optional[Port] = None) -> List[Interrupt]:
        """Gets the interrupts currently pending on one or both ports."""
        ports = [port] if port else [A, B]
        ints = []
        for port in ports:
            flags = self.read_port_interrupt(port)
            captures = self.read_port_interrupt_captured(port)
            for pin in range(8):
                if flags & (1 << pin):
                    ints.append(Interrupt(port, pin, port.number * 8 + pin, (captures >> pin) & 1))
        return ints

    def _check_ongoing_transaction(self):
        if self._configuring or self._reads is not None or self._writes is not None:
            raise RuntimeError("transaction already started")

    def begin_read(self):
        """Starts a read transaction.

        All reads made during the read transaction are cached at the time of the first read to
        the port containing the pin being read. The cache is cleared when ``end_read()`` is called.
        This is done automatically if ``begin_read()`` is used with a ``with`` statement.
        """
        self._reads = [None, None]
        return self._Reader(self)

    def end_read(self):
        """Ends a read transaction and clears the read cache."""
        if self._reads is None:
            raise RuntimeError("no read transaction started")
        self._reads = None

    def begin_write(self):
        """Starts a write transaction.

        All writes made during a write transaction are committed when ``end_write()`` is called.
        This is done automatically if ``begin_write()`` is used with a ``with`` statement.
        """
        self._check_ongoing_transaction()
        self._writes = self._outputs[:]
        return self._Writer(self)

    def end_write(self):
        """Ends a write transaction and commits all writes performed after the call to ``begin_write()``."""
        if self._writes is None:
            raise RuntimeError("no write transaction started")
        for port in [A, B]:
            if self._writes[port.number] != self._outputs[port.number]:
                self.write_port(port, self._writes[port.number], ignore_transaction=True)
        self._writes = None

    def begin_configuration(self):
        """Starts a configuration transaction.

        All configuration and write actions made during a configuration transaction are committed when
        ``end_configuration()`` is called. This is done automatically if ``begin_configuration()``
        is used with a ``with`` statement.
        """
        self._check_ongoing_transaction()
        self._configuring = True
        self._writes = self._outputs[:]
        return self._Configurer(self)

    def end_configuration(self):
        """Ends a configuration transaction and commits all configuration changes performed after
        the call to ``begin_configuration()``.
        """
        if not self._configuring:
            raise RuntimeError("no configuration transaction started")
        self._configuring = False
        self.set_io_configuration(self._iocon)
        for port in [A, B]:
            self.write_port(port, self._writes[port.number], ignore_transaction=True)
            self.set_port_invert(port, self._invs[port.number])
            self.set_port_pullup(port, self._pulls[port.number])
            self.set_port_direction(port, self._dirs[port.number])
            self.set_port_interrupt(port, self._inten[port.number], self._defval[port.number], self._intcon[port.number])
        self._writes = None

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
