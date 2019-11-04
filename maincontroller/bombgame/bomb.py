from enum import Enum
from threading import RLock, Condition
from time import sleep

from .bus.bus import BombBus
from .casings import Casing
from .events import BombWarning, BombInitFailure
from .gpio import Gpio, ModuleSenseChange
from .bus.messages import BusMessage, ResetMessage, AnnounceMessage, InitCompleteMessage, PingMessage, DefuseBombMessage, ExplodeBombMessage, ModuleId
from .modules.registry import MODULE_ID_REGISTRY
from .modules.base import ModuleState
from .modules.timer import TimerModule
from .utils import EventSource

class BombState(Enum):
    UNINITIALIZED = 0
    INITIALIZING_MODULES = 1
    MODULES_INITIALIZED = 2
    INITIALIZATION_FAILED = -1
    DEINITIALIZED = -2

class Bomb(EventSource):
    """
    The bomb, consisting of a casing and modules.
    """

    DEFAULT_MAX_STRIKES = 3

    def __init__(self, bus: BombBus, gpio: Gpio, casing: Casing, *, max_strikes=DEFAULT_MAX_STRIKES):
        super().__init__()
        self.bus = bus
        self._gpio = gpio
        self.casing = casing
        self.modules_by_bus_id = {}
        self.modules_by_location = {}
        self.max_strikes = max_strikes
        self.strikes = 0
        self.time_left = 0.0
        self.timer_speed = 1.0
        self._state = BombState.UNINITIALIZED
        self._init_location = None
        self._state_lock = RLock()
        self._init_cond = Condition(self._state_lock)
        bus.add_listener(BusMessage, self._receive_message)
        gpio.add_listener(ModuleSenseChange, self._sense_change)
        self.add_listener(BombInitFailure, self._init_fail)

    def _init_fail(self, _):
        with self._state_lock:
            self._state = BombState.INITIALIZATION_FAILED

    def _sense_change(self, _):
        if self._state != BombState.UNINITIALIZED:
            pass # TODO handle module changes

    def initialize(self):
        if self._state != BombState.UNINITIALIZED:
            raise RuntimeError("can't reinitialize used Bomb")
        self._state_lock.acquire()
        self._state = BombState.INITIALIZING_MODULES
        self._gpio.reset()
        connected_modules = self._gpio.check_sense_changes()
        self.bus.send(ResetMessage(ModuleId.BROADCAST))
        self._state_lock.release()
        sleep(0.5)
        self._state_lock.acquire()
        if self._state == BombState.INITIALIZATION_FAILED:
            return
        for location in connected_modules:
            self._gpio.set_enable(location, True)
            self._init_cond.wait_for(lambda: self.modules_by_location[location] is not None, timeout=1.0) # pylint: disable=cell-var-from-loop
            self._gpio.set_enable(location, False)
        if not any(isinstance(module, TimerModule) for module in self.modules_by_bus_id.values()):
            self.trigger(BombInitFailure("no timer found on bomb"))
            return
        with self._state_lock:
            # TODO cancellation mechanism, pinging
            self._init_cond.wait_for(lambda: self._state == BombState.MODULES_INITIALIZED)
        self._state_lock.release()

    def deinitialize(self):
        self.bus.remove_listener(BusMessage, self._receive_message)
        self._state = BombState.DEINITIALIZED

    def _receive_message(self, message: BusMessage):
        with self._state_lock:
            if self._state == BombState.UNINITIALIZED:
                return
            if isinstance(message, AnnounceMessage):
                if self._state != BombState.INITIALIZING_MODULES:
                    self.trigger(BombWarning(f"announce from {message.module} after bomb initialization"))
                    # TODO implement module hotswap
                    return
                if message.module in self.modules_by_bus_id:
                    self.trigger(BombInitFailure(f"duplicate module with id {message.module}"))
                    return
                if self._init_location is None:
                    self.trigger(BombInitFailure(f"unrequested announce from {message.module}"))
                module = MODULE_ID_REGISTRY[message.module.type](self, message.module, self._init_location)
                if message.init_complete:
                    module.state = ModuleState.CONFIGURATION
                self.modules_by_bus_id[message.module] = module
                self._init_location = None
                self._init_cond.notify_all()
                return
            module = self.modules_by_bus_id.get(message.module)
            if module is None:
                self.trigger(BombWarning(f"{message.__class__.__name__} received from unknown module {message.module}"))
                return
            if isinstance(message, InitCompleteMessage) and module.state == ModuleState.INITIALIZATION:
                module.state = ModuleState.CONFIGURATION
                if self._state == BombState.INITIALIZING_MODULES and all(module.state == ModuleState.CONFIGURATION for module in self.modules_by_bus_id.values()):
                    self._state = BombState.MODULES_INITIALIZED
                    self._init_cond.notify_all()
                return
            if isinstance(message, PingMessage) and module.ping_time is not None:
                module.ping_time = None
        self.trigger(BombWarning(f"{message.__class__.__name__} received from {message.module} in an invalid state"))

    def explode(self):
        self.bus.send(ExplodeBombMessage(ModuleId.BROADCAST))

    def defuse(self):
        self.bus.send(DefuseBombMessage(ModuleId.BROADCAST))

    def strike(self) -> bool:
        """Increments the strike count. Returns True if the bomb exploded."""
        self.strikes += 1
        if self.strikes >= self.max_strikes:
            self.explode()
            return True
        return False
