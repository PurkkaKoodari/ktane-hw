from asyncio import (Lock, Condition, TimeoutError as AsyncTimeoutError, create_task, shield, sleep as async_sleep,
                     wait_for, Task)
from time import monotonic
from typing import List, Dict, Optional

from bombgame.bomb.serial import BombSerial
from bombgame.bomb.state import BombState
from bombgame.bus.bus import BombBus
from bombgame.bus.messages import (BusMessage, ResetMessage, AnnounceMessage, InitCompleteMessage, PingMessage,
                                   DefuseBombMessage, ExplodeBombMessage, ModuleId)
from bombgame.casings import Casing
from bombgame.events import (BombErrorLevel, BombError, BombModuleAdded, ModuleStateChanged, BombStateChanged,
                             ModuleStriked)
from bombgame.gpio import AbstractGpio, ModuleReadyChange
from bombgame.modules.base import ModuleState, Module
from bombgame.modules.registry import MODULE_ID_REGISTRY
from bombgame.modules.timer import TimerModule
from bombgame.utils import EventSource

MODULE_RESET_PERIOD = 0.5
MODULE_ANNOUNCE_TIMEOUT = 1.0
MODULE_PING_INTERVAL = 1.0
MODULE_PING_TIMEOUT = 1.0

GAME_START_DELAY = 5


class Bomb(EventSource):
    """
    The bomb, consisting of a casing and modules.
    """

    DEFAULT_MAX_STRIKES = 3

    bus: BombBus
    casing: Casing
    modules: List[Module]
    modules_by_bus_id: Dict[ModuleId, Module]
    modules_by_location: Dict[int, Module]
    max_strikes: int
    strikes: int
    time_left: float
    timer_speed: float
    widgets: list  # TODO fix the type
    serial_number: BombSerial
    _state: BombState
    _init_location: Optional[int]
    _state_lock: Lock
    _init_cond: Condition
    _gpio: AbstractGpio
    _running_tasks: List[Task]

    def __init__(self, bus: BombBus, gpio: AbstractGpio, casing: Casing, *, max_strikes: int = DEFAULT_MAX_STRIKES, serial_number: str = None):
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
        self.widgets = []  # TODO fill and control these
        self.serial_number = BombSerial(serial_number)  # TODO display this somewhere
        self._state = BombState.UNINITIALIZED
        self._init_location = None
        self._state_lock = Lock()
        self._init_cond = Condition(self._state_lock)
        self._running_tasks = []
        bus.add_listener(BusMessage, self._receive_message)
        gpio.add_listener(ModuleReadyChange, self._module_ready_change)

    async def initialize(self):
        if self._state != BombState.UNINITIALIZED:
            raise RuntimeError("Bomb already initialized")
        await self._state_lock.acquire()
        self._state = BombState.RESETTING
        # reset enable and widget pins
        await self._gpio.reset()
        # send reset to all modules
        await self.bus.send(ResetMessage(ModuleId.BROADCAST))
        # wait for modules to reset
        self._state_lock.release()
        await async_sleep(MODULE_RESET_PERIOD)
        await self._state_lock.acquire()
        # get modules that are ready
        connected_modules = await self._gpio.check_ready_changes()
        self._state = BombState.INITIALIZING
        # initialize each module in order
        for location in connected_modules:
            # check that we have not failed yet
            if self._state == BombState.INITIALIZATION_FAILED:
                return
            # initialize a module
            await self._gpio.set_enable(location, True)
            try:
                await wait_for(shield(self._init_cond.wait_for(lambda: self.modules_by_location[location] is not None)), MODULE_ANNOUNCE_TIMEOUT)  # pylint: disable=cell-var-from-loop
            except AsyncTimeoutError:
                self._init_fail(f"module at {self.casing.location(location)} did not announce in time")
                return
            await self._gpio.set_enable(location, False)
        # check that we have a timer module somewhere
        if not any(isinstance(module, TimerModule) for module in self.modules_by_bus_id.values()):
            self._init_fail("no timer found on bomb")
            return
        # start pinging modules that have not sent anything in a while
        self.create_task(self._ping_loop())
        # wait for all modules to initialize
        await self._init_cond.wait_for(lambda: self._state == BombState.INITIALIZED)
        self._state_lock.release()
        self.trigger(BombStateChanged(BombState.INITIALIZED))

    def deinitialize(self):
        if self._state == BombState.DEINITIALIZED:
            raise RuntimeError("Bomb already deinitialized")
        for task in self._running_tasks:
            task.cancel()
        self.bus.remove_listener(BusMessage, self._receive_message)
        self._gpio.remove_listener(ModuleReadyChange, self._module_ready_change)
        self._state = BombState.DEINITIALIZED

    def create_task(self, task):
        task = create_task(task)
        self._running_tasks.append(task)
        return task

    def cancel_task(self, task):
        task.cancel()
        self._running_tasks.remove(task)

    def _module_ready_change(self, change: ModuleReadyChange):
        if self._state != BombState.UNINITIALIZED:
            if change.present:
                self.trigger(BombError(None, BombErrorLevel.WARNING, f"A module was added at {self.casing.location(change.location)} after initialization."))
            else:
                module = self.modules_by_location.get(change.location)
                if module is None:
                    self.trigger(BombError(None, BombErrorLevel.WARNING, f"A module was removed at {self.casing.location(change.location)} after initialization."))
                else:
                    self.trigger(BombError(module, BombErrorLevel.WARNING, f"Module was removed after initialization."))

    def _init_fail(self, reason):
        self._state = BombState.INITIALIZATION_FAILED
        self.trigger(BombError(None, BombErrorLevel.INIT_FAILURE, reason))

    async def _receive_message(self, message: BusMessage):
        async with self._state_lock:
            if self._state == BombState.UNINITIALIZED or self._state == BombState.RESETTING or self._state == BombState.DEINITIALIZED:
                return
            if isinstance(message, AnnounceMessage):
                if self._state != BombState.INITIALIZING:
                    # TODO implement module hotswap
                    self.trigger(BombError(None, BombErrorLevel.WARNING, f"{message.module} was announced after initialization."))
                    return
                if message.module in self.modules_by_bus_id:
                    self._init_fail(f"Multiple modules were announced with id {message.module}.")
                    return
                if self._init_location is None:
                    self._init_fail(f"An unrequested announce was received from {message.module}.")
                    return
                module = MODULE_ID_REGISTRY[message.module.type](self, message.module, self._init_location, message.hw_version, message.sw_version)
                if message.init_complete:
                    module.state = ModuleState.CONFIGURATION
                self.modules_by_bus_id[message.module] = module
                self.modules_by_location[self._init_location] = module
                self.modules.append(module)
                self.trigger(BombModuleAdded(module))
                module.add_listener(ModuleStateChanged, self._check_solve)
                self._init_location = None
                self._init_cond.notify_all()
                return
            module = self.modules_by_bus_id.get(message.module)
            if module is None:
                self.trigger(BombError(None, BombErrorLevel.WARNING, f"Received {message.__class__.__name__} from unannounced module {message.module}."))
                return
            module.last_received = monotonic()
            if isinstance(message, InitCompleteMessage) and module.state == ModuleState.INITIALIZATION:
                module.state = ModuleState.CONFIGURATION
                self.trigger(ModuleStateChanged(module))
                if self._state == BombState.INITIALIZING and all(module.state == ModuleState.CONFIGURATION for module in self.modules_by_bus_id.values()):
                    self._state = BombState.INITIALIZED
                    self._init_cond.notify_all()
                return
            if isinstance(message, PingMessage) and module.last_ping_sent is not None:
                module.last_ping_sent = None
                return
            self.trigger(BombError(module, BombErrorLevel.WARNING, f"Received {message.__class__.__name__} in an invalid state."))

    async def _ping_loop(self):
        while True:
            now = monotonic()
            for module in self.modules:
                if module.last_ping_sent is not None and now > module.last_ping_sent + MODULE_PING_TIMEOUT:
                    # TODO module auto-restart?
                    self.trigger(BombError(module, BombErrorLevel.WARNING, "Ping timeout."))
                elif module.last_ping_sent is None and now > module.last_received + MODULE_PING_INTERVAL:
                    await self.bus.send(PingMessage(module.bus_id))
            await async_sleep(0.1)

    async def start_game(self):
        """Starts the game with the initial wait phase."""
        self.create_task(self._start_game_task())

    async def _start_game_task(self):
        for module in self.modules:
            await module.send_state()
        self._state = BombState.GAME_STARTING
        self.trigger(BombStateChanged(BombState.GAME_STARTING))
        # TODO: add at least an option to manually do the starting from UI
        await async_sleep(GAME_START_DELAY)
        self._state = BombState.GAME_STARTED
        self.trigger(BombStateChanged(BombState.GAME_STARTED))

    async def explode(self):
        """Ends the game by exploding the bomb."""
        self._state = BombState.EXPLODED
        self.trigger(BombStateChanged(BombState.EXPLODED))
        await self.bus.send(ExplodeBombMessage(ModuleId.BROADCAST))
        # TODO: play sounds here; room-scale effects will react to the BombStateChanged event

    async def _check_solve(self, _: ModuleStateChanged):
        if all(module.state == ModuleState.DEFUSED or not module.must_solve for module in self.modules):
            self._state = BombState.DEFUSED
            self.trigger(BombStateChanged(BombState.DEFUSED))
            await self.bus.send(DefuseBombMessage(ModuleId.BROADCAST))

    async def strike(self, module: Module) -> bool:
        """Called by modules to indicate a strike.

        Returns ``True`` if the bomb exploded due to the strike, in which case the module should immediately stop
        sending messages to the bus.
        """
        self.strikes += 1
        if self.strikes >= self.max_strikes:
            await self.explode()
            return True
        self.trigger(ModuleStriked(module))
        # TODO play strike sound
        return False
