from enum import Enum
from time import monotonic
from asyncio import Lock, Condition, TimeoutError as AsyncTimeoutError, create_task, shield, sleep as async_sleep, wait_for

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

MODULE_RESET_PERIOD = 0.5
MODULE_ANNOUNCE_TIMEOUT = 1.0
MODULE_PING_INTERVAL = 1.0
MODULE_PING_TIMEOUT = 1.0

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
        self.modules = []
        self.modules_by_bus_id = {}
        self.modules_by_location = {}
        self.max_strikes = max_strikes
        self.strikes = 0
        self.time_left = 0.0
        self.timer_speed = 1.0
        self._state = BombState.UNINITIALIZED
        self._init_location = None
        self._state_lock = Lock()
        self._init_cond = Condition(self._state_lock)
        self._pinger = None
        bus.add_listener(BusMessage, self._receive_message)
        gpio.add_listener(ModuleSenseChange, self._sense_change)

    def _sense_change(self, _):
        if self._state != BombState.UNINITIALIZED:
            pass # TODO handle module changes

    async def initialize(self):
        if self._state != BombState.UNINITIALIZED:
            raise RuntimeError("can't reinitialize used Bomb")
        # reset GPIO and get currently connected modules
        await self._state_lock.acquire()
        self._state = BombState.INITIALIZING_MODULES
        await self._gpio.reset()
        connected_modules = await self._gpio.check_sense_changes()
        # send reset to all modules
        await self.bus.send(ResetMessage(ModuleId.BROADCAST))
        # wait for modules to reset
        self._state_lock.release()
        await async_sleep(MODULE_RESET_PERIOD)
        await self._state_lock.acquire()
        # initialize each module in order
        for location in connected_modules:
            # check that we have not failed yet
            if self._state == BombState.INITIALIZATION_FAILED:
                return
            # initialize a module
            await self._gpio.set_enable(location, True)
            try:
                await wait_for(shield(self._init_cond.wait_for(lambda: self.modules_by_location[location] is not None)), MODULE_ANNOUNCE_TIMEOUT) # pylint: disable=cell-var-from-loop
            except AsyncTimeoutError:
                self._init_fail(f"module at {self.casing.location(location)} did not announce in time")
                return
            await self._gpio.set_enable(location, False)
        # check that we have a timer module somewhere
        if not any(isinstance(module, TimerModule) for module in self.modules_by_bus_id.values()):
            self._init_fail("no timer found on bomb")
            return
        # wait for all modules to initialize
        await self._init_cond.wait_for(lambda: self._state == BombState.MODULES_INITIALIZED)
        self._state_lock.release()
        self._pinger = create_task(self._ping_loop())

    def stop(self):
        if self._pinger is not None:
            self._pinger.cancel()
        self.bus.remove_listener(BusMessage, self._receive_message)
        self._gpio.remove_listener(ModuleSenseChange, self._sense_change)
        self._state = BombState.DEINITIALIZED

    def _init_fail(self, reason):
        self._state = BombState.INITIALIZATION_FAILED
        self.trigger(BombInitFailure(reason))

    async def _receive_message(self, message: BusMessage):
        async with self._state_lock:
            if self._state == BombState.UNINITIALIZED:
                return
            if isinstance(message, AnnounceMessage):
                if self._state != BombState.INITIALIZING_MODULES:
                    # TODO implement module hotswap
                    self.trigger(BombWarning(f"late announce from {message.module}"))
                    return
                if message.module in self.modules_by_bus_id:
                    self._init_fail(f"duplicate module with id {message.module}")
                    return
                if self._init_location is None:
                    self._init_fail(f"unrequested announce from {message.module}")
                    return
                module = MODULE_ID_REGISTRY[message.module.type](self, message.module, self._init_location, message.hw_version, message.sw_version)
                if message.init_complete:
                    module.state = ModuleState.CONFIGURATION
                self.modules_by_bus_id[message.module] = module
                self.modules_by_location[self._init_location] = module
                self.modules.append(module)
                self._init_location = None
                self._init_cond.notify_all()
                return
            module = self.modules_by_bus_id.get(message.module)
            if module is None:
                self.trigger(BombWarning(f"{message.__class__.__name__} from unannounced {message.module}"))
                return
            module.last_received = monotonic()
            if isinstance(message, InitCompleteMessage) and module.state == ModuleState.INITIALIZATION:
                module.state = ModuleState.CONFIGURATION
                if self._state == BombState.INITIALIZING_MODULES and all(module.state == ModuleState.CONFIGURATION for module in self.modules_by_bus_id.values()):
                    self._state = BombState.MODULES_INITIALIZED
                    self._init_cond.notify_all()
                return
            if isinstance(message, PingMessage) and module.last_ping_sent is not None:
                module.last_ping_sent = None
                return
            self.trigger(BombWarning(f"{message.__class__.__name__} from {message.module} in an invalid state"))

    async def _ping_loop(self):
        while True:
            now = monotonic()
            for module in self.modules:
                if module.last_ping_sent is not None and now > module.last_ping_sent + MODULE_PING_TIMEOUT:
                    # TODO module auto-restart?
                    self.trigger(BombWarning(f"ping timeout for {module.bus_id}"))
                elif module.last_ping_sent is None and now > module.last_received + MODULE_PING_INTERVAL:
                    await self.bus.send(PingMessage(module.bus_id))
            await async_sleep(0.1)

    async def explode(self):
        """Sends the explode message to all modules."""
        await self.bus.send(ExplodeBombMessage(ModuleId.BROADCAST))

    async def defuse(self):
        """Sends the defuse message to all modules."""
        await self.bus.send(DefuseBombMessage(ModuleId.BROADCAST))

    async def strike(self) -> bool:
        """Increments the strike count. Returns True if the bomb exploded."""
        self.strikes += 1
        if self.strikes >= self.max_strikes:
            await self.explode()
            return True
        return False
