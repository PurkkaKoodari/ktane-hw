import struct

from .base import Module
from .registry import MODULE_ID_REGISTRY, MODULE_MESSAGE_ID_REGISTRY
from ..bus.messages import BusMessage, BusMessageId, ModuleId, BusMessageDirection

@MODULE_ID_REGISTRY.register
class TimerModule(Module):
    module_id = 1

    def __init__(self, bomb, bus_id):
        super().__init__(bomb, bus_id)
        # TODO listen to timer ticks

    def generate(self):
        pass

@MODULE_MESSAGE_ID_REGISTRY.register
class SetTimerStateMessage(BusMessage):
    message_id = (TimerModule, BusMessageId.MODULE_SPECIFIC_0)

    __slots__ = ("secs", "speed", "strikes", "max_strikes")

    def __init__(self, module: ModuleId, direction: BusMessageDirection = BusMessageDirection.OUT, *,
                 time_left: float, speed: float, strikes: int, max_strikes: int):
        super().__init__(self.__class__.message_id[1], module, direction)
        self.secs = round(time_left)
        self.speed = int(speed * 256)
        self.strikes = strikes
        self.max_strikes = max_strikes

    @classmethod
    def _parse_data(cls, module: ModuleId, direction: BusMessageDirection, data: bytes):
        if len(data) != 6:
            raise ValueError(f"{cls.__name__} must have 6 bytes of data")
        secs, speed, strikes, max_strikes = struct.unpack("<HHBB")
        return cls(module, direction, time_left=secs, speed=speed / 256, strikes=strikes, max_strikes=max_strikes)

    def _serialize_data(self):
        return struct.pack("<HHBB", self.secs, self.speed, self.strikes, self.max_strikes)
