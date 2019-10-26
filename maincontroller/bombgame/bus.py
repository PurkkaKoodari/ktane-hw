from abc import ABC, abstractclassmethod, abstractmethod
from enum import IntEnum
from typing import Tuple
import struct

import can

from .utils import EventSource, Registry, Ungettable

MODULEID_TYPE_BITS = 12
MODULEID_SERIAL_BITS = 10
MODULEID_TYPE_MAX = (1 << MODULEID_TYPE_BITS) - 1
MODULEID_SERIAL_MAX = (1 << MODULEID_SERIAL_BITS) - 1

class ModuleId:
    """
    A module identifier as used on the bus.
    """

    def __init__(self, type_: int, serial: int):
        if not 0 <= type_ <= MODULEID_TYPE_MAX:
            raise ValueError(f"type must be between 0 and {MODULEID_TYPE_MAX}")
        if not 0 <= serial <= MODULEID_SERIAL_MAX:
            raise ValueError(f"serial must be between 0 and {MODULEID_SERIAL_MAX}")
        if type_ == 0 and serial != 0:
            raise ValueError("serial must be 0 if type is 0")
        self.type = type_
        self.serial = serial

    def is_broadcast(self):
        return self.type == 0

    def __int__(self):
        return (self.type << MODULEID_SERIAL_BITS) | self.serial

    def __eq__(self, other):
        return isinstance(other, ModuleId) and other.type == self.type and other.serial == self.serial

    def __hash__(self):
        return self.__int__()

ModuleId.BROADCAST = ModuleId(0, 0)

class BusMessageId(IntEnum):
    RESET = 0x00
    ANNOUNCE = 0x01
    INITIALIZE = 0x02
    PING = 0x03
    LAUNCH_GAME = 0x10
    START_TIMER = 0x11
    EXPLODE = 0x12
    DEFUSE = 0x13
    STRIKE = 0x14
    SOLVE = 0x15
    NEEDY_ACTIVATE = 0x16
    NEEDY_DEACTIVATE = 0x17
    RECOVERABLE_ERROR = 0x20
    RECOVERED_ERROR = 0x21
    MINOR_UNRECOVERABLE_ERROR = 0x22
    MAJOR_UNRECOVERABLE_ERROR = 0x23
    MODULE_SPECIFIC_0 = 0x30
    MODULE_SPECIFIC_1 = 0x31
    MODULE_SPECIFIC_2 = 0x32
    MODULE_SPECIFIC_3 = 0x33
    MODULE_SPECIFIC_4 = 0x34
    MODULE_SPECIFIC_5 = 0x35
    MODULE_SPECIFIC_6 = 0x36
    MODULE_SPECIFIC_7 = 0x37
    MODULE_SPECIFIC_8 = 0x38
    MODULE_SPECIFIC_9 = 0x39
    MODULE_SPECIFIC_A = 0x3A
    MODULE_SPECIFIC_B = 0x3B
    MODULE_SPECIFIC_C = 0x3C
    MODULE_SPECIFIC_D = 0x3D
    MODULE_SPECIFIC_E = 0x3E
    MODULE_SPECIFIC_F = 0x3F

class BusMessageDirection(IntEnum):
    OUT = 0
    IN = 1

MESSAGE_DIRECTION_BITS = 1
MESSAGE_MODULE_TYPE_BITS = 12
MESSAGE_MODULE_SERIAL_BITS = 10
MESSAGE_ID_BITS = 6

MESSAGE_DIRECTION_OFFSET = 28
MESSAGE_MODULE_TYPE_OFFSET = 16
MESSAGE_MODULE_SERIAL_OFFSET = 6
MESSAGE_ID_OFFSET = 0

MESSAGE_DIRECTION_MASK = ((1 << MESSAGE_DIRECTION_BITS) - 1) << MESSAGE_DIRECTION_OFFSET
MESSAGE_MODULE_TYPE_MASK = ((1 << MESSAGE_MODULE_TYPE_BITS) - 1) << MESSAGE_MODULE_TYPE_OFFSET
MESSAGE_MODULE_SERIAL_MASK = ((1 << MESSAGE_MODULE_SERIAL_BITS) - 1) << MESSAGE_MODULE_SERIAL_OFFSET
MESSAGE_ID_MASK = ((1 << MESSAGE_ID_BITS) - 1) << MESSAGE_ID_OFFSET

MESSAGE_ID_REGISTRY = Registry("message_id")

class BusMessage(ABC):
    __slots__ = ("id", "module", "direction")

    message_id = Ungettable

    def __init__(self, id_: BusMessageId, module: ModuleId, direction: BusMessageDirection = BusMessageDirection.OUT):
        if MESSAGE_ID_REGISTRY[id_] != self.__class__:
            raise ValueError("incorrect message class for id")
        if module.is_broadcast() and direction != BusMessageDirection.OUT:
            raise ValueError("broadcast messages must be outward")

        self.id = id_
        self.module = module
        self.direction = direction

    @classmethod
    def parse(cls, message: can.Message) -> "BusMessage":
        if not message.is_extended_id:
            raise ValueError("invalid message: non-extended arbitration id")

        direction = (message.arbitration_id & MESSAGE_DIRECTION_MASK) >> MESSAGE_DIRECTION_OFFSET
        module_type = (message.arbitration_id & MESSAGE_MODULE_TYPE_MASK) >> MESSAGE_MODULE_TYPE_OFFSET
        module_serial = (message.arbitration_id & MESSAGE_MODULE_SERIAL_MASK) >> MESSAGE_MODULE_SERIAL_OFFSET
        message_id = (message.arbitration_id & MESSAGE_ID_MASK) >> MESSAGE_ID_OFFSET

        direction = BusMessageDirection(direction)
        module_id = ModuleId(module_type, module_serial)

        if message_id >= BusMessageId.MODULE_SPECIFIC_0:
            from .modules import MODULE_ID_REGISTRY, MODULE_MESSAGE_ID_REGISTRY
            if module_id.type not in MODULE_ID_REGISTRY:
                raise ValueError(f"invalid message: unknown module type {hex(module_id.type)}")
            module_type = MODULE_ID_REGISTRY[module_id.type]
            lookup = (module_type, message_id)
            if lookup not in MODULE_MESSAGE_ID_REGISTRY:
                raise ValueError(f"invalid message: unknown message id {hex(message_id)} for {module_type.__name__}")
            message_class = MODULE_MESSAGE_ID_REGISTRY[lookup]
        else:
            if message_id not in MESSAGE_ID_REGISTRY:
                raise ValueError(f"invalid message: unknown message id {hex(message_id)}")
            message_class = MESSAGE_ID_REGISTRY[message_id]

        return message_class._parse_data(module_id, direction, message.data)

    def serialize(self) -> can.Message:
        arbitration_id = ((self.direction << MESSAGE_DIRECTION_OFFSET)
                          | (self.module.type << MESSAGE_MODULE_TYPE_OFFSET)
                          | (self.module.serial << MESSAGE_MODULE_SERIAL_OFFSET)
                          | (self.id << MESSAGE_ID_OFFSET))
        data = self._serialize_data()
        return can.Message(arbitration_id=arbitration_id, is_extended_id=True, data=data, check=True)

    @abstractclassmethod
    def _parse_data(cls, module: ModuleId, direction: BusMessageDirection, data: bytes):
        pass

    @abstractmethod
    def _serialize_data(self):
        pass

class SimpleBusMessage(BusMessage):
    def __init__(self, module: ModuleId, direction: BusMessageDirection = BusMessageDirection.OUT):
        super().__init__(self.__class__.message_id, module, direction)

    @classmethod
    def _parse_data(cls, module: ModuleId, direction: BusMessageDirection, data: bytes):
        if data:
            raise ValueError(f"no data allowed for {cls.__name__}")
        return cls(module, direction)

    def _serialize_data(self):
        return b""

class VersionMessage(BusMessage):
    __slots__ = ("hw_version", "sw_version")

    def __init__(self, module: ModuleId, direction: BusMessageDirection = BusMessageDirection.OUT, *,
                 hw_version: Tuple[int], sw_version: Tuple[int]):
        super().__init__(self.__class__.message_id, module, direction)
        self.hw_version = hw_version
        self.sw_version = sw_version

    @classmethod
    def _parse_data(cls, module: ModuleId, direction: BusMessageDirection, data: bytes):
        if len(data) != 4:
            raise ValueError(f"{cls.__name__} must have 4 bytes of data")
        hw_major, hw_minor, sw_major, sw_minor = struct.unpack(">BBBB", data)
        return cls(module, direction, hw_version=(hw_major, hw_minor), sw_version=(sw_major, sw_minor))

    def _serialize_data(self):
        return struct.pack(">BBBB", *self.hw_version, *self.sw_version)

class StatusMessage(SimpleBusMessage):
    pass

class BombStatusMessage(StatusMessage):
    pass

class ModuleStatusMessage(StatusMessage):
    pass

class ErrorMessage(StatusMessage):
    __slots__ = ("code", "details")

    def __init__(self, module: ModuleId, direction: BusMessageDirection = BusMessageDirection.OUT, *, code: int, details: bytes):
        super().__init__(self.__class__.message_id, module, direction)
        if len(details) > 7:
            raise ValueError("error details must be up to 7 bytes")
        self.code = code
        self.details = details

    @classmethod
    def _parse_data(cls, module: ModuleId, direction: BusMessageDirection, data: bytes):
        if not 1 <= len(data) <= 8:
            raise ValueError(f"{cls.__name__} must have 1 to 8 bytes of data")
        code, = struct.unpack_from(">B", data, 0)
        return cls(module, direction, code=code, details=data[1:])

    def _serialize_data(self):
        return struct.pack(">B", self.code) + self.details

@MESSAGE_ID_REGISTRY.register
class ResetMessage(SimpleBusMessage):
    message_id = BusMessageId.RESET

@MESSAGE_ID_REGISTRY.register
class AnnounceMessage(VersionMessage):
    message_id = BusMessageId.ANNOUNCE

@MESSAGE_ID_REGISTRY.register
class InitializeMessage(VersionMessage):
    message_id = BusMessageId.INITIALIZE

@MESSAGE_ID_REGISTRY.register
class PingMessage(SimpleBusMessage):
    message_id = BusMessageId.PING

@MESSAGE_ID_REGISTRY.register
class LaunchGameMessage(BombStatusMessage):
    message_id = BusMessageId.LAUNCH_GAME

@MESSAGE_ID_REGISTRY.register
class StartTimerMessage(BombStatusMessage):
    message_id = BusMessageId.START_TIMER

@MESSAGE_ID_REGISTRY.register
class ExplodeBombMessage(BombStatusMessage):
    message_id = BusMessageId.EXPLODE

@MESSAGE_ID_REGISTRY.register
class DefuseBombMessage(BombStatusMessage):
    message_id = BusMessageId.DEFUSE

@MESSAGE_ID_REGISTRY.register
class StrikeModuleMessage(ModuleStatusMessage):
    message_id = BusMessageId.STRIKE

@MESSAGE_ID_REGISTRY.register
class SolveModuleMessage(ModuleStatusMessage):
    message_id = BusMessageId.SOLVE

@MESSAGE_ID_REGISTRY.register
class NeedyActivateMessage(ModuleStatusMessage):
    message_id = BusMessageId.NEEDY_ACTIVATE

@MESSAGE_ID_REGISTRY.register
class NeedyDeactivateMessage(ModuleStatusMessage):
    message_id = BusMessageId.NEEDY_DEACTIVATE

@MESSAGE_ID_REGISTRY.register
class RecoverableErrorMessage(ErrorMessage):
    message_id = BusMessageId.RECOVERABLE_ERROR

@MESSAGE_ID_REGISTRY.register
class RecoveredErrorMessage(ErrorMessage):
    message_id = BusMessageId.RECOVERED_ERROR

@MESSAGE_ID_REGISTRY.register
class MinorUnrecoverableErrorMessage(ErrorMessage):
    message_id = BusMessageId.MINOR_UNRECOVERABLE_ERROR

@MESSAGE_ID_REGISTRY.register
class MajorUnrecoverableErrorMessage(ErrorMessage):
    message_id = BusMessageId.MAJOR_UNRECOVERABLE_ERROR

class BombBus(EventSource):
    """The CAN-based bus used for controlling the physical bomb.

    Listen for suitable BusMessage events to get incoming messages.
    """

    def __init__(self, bus: can.BusABC):
        super().__init__()
        self._bus = bus

    def send(self, message: BusMessage):
        """Send a message to the bus.

        :raises IOError:
            if the message could not be sent
        """
        try:
            self._bus.send(message.serialize())
        except can.CanError:
            raise IOError("failed to send message")

    def receive(self, message: can.Message):
        """Called by the CAN receiver thread when a message arrives."""
        message = BusMessage.parse(message)
        self.trigger(message)
