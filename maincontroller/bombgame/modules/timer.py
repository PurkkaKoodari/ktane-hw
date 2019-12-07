import struct

from bombgame.bus.messages import BusMessage, BusMessageId, ModuleId, BusMessageDirection
from bombgame.events import TimerTick, ModuleStriked
from bombgame.modules.base import Module
from bombgame.modules.registry import MODULE_ID_REGISTRY, MODULE_MESSAGE_ID_REGISTRY


@MODULE_ID_REGISTRY.register
class TimerModule(Module):
    module_id = 1
    must_solve = False

    def __init__(self, bomb, bus_id, location, hw_version, sw_version):
        super().__init__(bomb, bus_id, location, hw_version, sw_version)
        bomb.add_listener(TimerTick, self._update_timer)
        bomb.add_listener(ModuleStriked, self._update_timer)

    def generate(self):
        pass

    async def send_state(self):
        await self._update_timer(None)

    def ui_state(self):
        return None

    async def _update_timer(self, _):
        await self._bomb.bus.send(SetTimerStateMessage(
            self.bus_id,
            time_left=self._bomb.time_left,
            speed=self._bomb.timer_speed,
            strikes=self._bomb.strikes,
            max_strikes=self._bomb.max_strikes
        ))


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
        secs, speed, strikes, max_strikes = struct.unpack("<HHBB", data)
        return cls(module, direction, time_left=secs, speed=speed / 256, strikes=strikes, max_strikes=max_strikes)

    def _serialize_data(self):
        return struct.pack("<HHBB", self.secs, self.speed, self.strikes, self.max_strikes)

    def _data_repr(self):
        return f"{self.secs}s remaining, speed {self.speed}x, {self.strikes}/{self.max_strikes} strikes"
