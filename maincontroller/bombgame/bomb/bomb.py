from asyncio import (Lock, Condition, TimeoutError as AsyncTimeoutError, create_task, sleep as async_sleep,
                     wait_for, Task)
from logging import getLogger
from time import monotonic
from typing import List, Dict, Optional, Coroutine

from bombgame.audio import register_sound, AudioLocation, BombSoundSystem
from bombgame.bomb.edgework import Edgework
from bombgame.bomb.state import BombState
from bombgame.bus.bus import BombBus
from bombgame.bus.messages import (BusMessage, ResetMessage, AnnounceMessage, DefuseBombMessage, ExplodeBombMessage,
                                   ModuleId, LaunchGameMessage, StartTimerMessage)
from bombgame.casings import Casing
from bombgame.config import GAME_START_DELAY, MODULE_RESET_PERIOD, MODULE_ANNOUNCE_TIMEOUT, DEFAULT_MAX_STRIKES
from bombgame.events import (BombErrorLevel, BombError, BombModuleAdded, ModuleStateChanged, BombStateChanged,
                             ModuleStriked, TimerTick)
from bombgame.gpio import AbstractGpio, ModuleReadyChange
from bombgame.modules.base import ModuleState, Module
from bombgame.modules.registry import MODULE_ID_REGISTRY
from bombgame.modules.timer import TimerModule
from bombgame.utils import EventSource, log_errors

LOGGER = getLogger("Bomb")


class Bomb(EventSource):
    """
    The bomb, consisting of a casing and modules.
    """

    _bus: BombBus
    sound_system: BombSoundSystem
    casing: Casing
    modules: List[Module]
    modules_by_bus_id: Dict[ModuleId, Module]
    modules_by_location: Dict[int, Module]
    max_strikes: int
    strikes: int
    time_left: float
    timer_speed: float
    edgework: Edgework
    _state: BombState
    _init_location: Optional[int]
    _state_lock: Lock
    _init_cond: Condition
    _gpio: AbstractGpio
    _running_tasks: List[Task]

    def __init__(self, bus: BombBus, gpio: AbstractGpio, sound_system: BombSoundSystem, casing: Casing):
        super().__init__()
        self._bus = bus
        self._gpio = gpio
        self.sound_system = sound_system
        self.casing = casing
        self.modules = []
        self.modules_by_bus_id = {}
        self.modules_by_location = {}
        self.max_strikes = DEFAULT_MAX_STRIKES
        self.strikes = 0
        self.time_left = 0.0
        self.timer_speed = 1.0
        self.edgework = Edgework()
        self._state = BombState.UNINITIALIZED
        self._init_location = None
        self._state_lock = Lock()
        self._init_cond = Condition(self._state_lock)
        self._last_timer_update = 0.0
        self._running_tasks = []
        bus.add_listener(BusMessage, self._receive_message)
        gpio.add_listener(ModuleReadyChange, self._module_ready_change)
        self.add_listener(ModuleStateChanged, self._handle_module_state_change)

    async def initialize(self):
        if self._state != BombState.UNINITIALIZED:
            raise RuntimeError("Bomb already initialized")
        self.sound_system.stop_all_sounds()
        await self._state_lock.acquire()
        LOGGER.debug("Resetting all modules")
        self._state = BombState.RESETTING
        # reset enable and widget pins
        await self._gpio.reset()
        # send reset to all modules
        await self._bus.send(ResetMessage(ModuleId.BROADCAST))
        # wait for modules to reset
        self._state_lock.release()
        await async_sleep(MODULE_RESET_PERIOD)
        await self._state_lock.acquire()
        # get modules that are ready
        connected_modules = await self._gpio.check_ready_changes()
        LOGGER.debug("Detected %d modules", len(connected_modules))
        self._state = BombState.INITIALIZING
        # initialize each module in order
        for location in connected_modules:
            LOGGER.debug("Initializing module at %s", self.casing.location(location))
            # check that we have not failed yet
            if self._state == BombState.INITIALIZATION_FAILED:
                return
            # initialize a module
            self._init_location = location
            await self._gpio.set_enable(location, True)
            try:
                await wait_for(self._init_cond.wait_for(lambda: location in self.modules_by_location), MODULE_ANNOUNCE_TIMEOUT)  # pylint: disable=cell-var-from-loop
            except AsyncTimeoutError:
                self._init_fail(f"module at {self.casing.location(location)} did not announce in time")
                return
            finally:
                await self._gpio.set_enable(location, False)
        self._init_location = None
        # check that we have a timer module somewhere
        if not any(isinstance(module, TimerModule) for module in self.modules):
            self._init_fail("no timer found on bomb")
            return
        # start pinging modules that have not sent anything in a while
        self.create_task(self._ping_loop())
        # load sounds for the modules
        # TODO do this in an auxiliary thread (but that will require us to move all audio stuff in said thread)
        self.sound_system.load_sounds({Bomb} | set(type(module) for module in self.modules))
        # wait for all modules to initialize
        if not all(module.state == ModuleState.CONFIGURATION for module in self.modules):
            LOGGER.debug("All modules recognized, waiting for initialization")
            await self._init_cond.wait_for(lambda: self._state == BombState.INITIALIZED)
        self._state_lock.release()
        LOGGER.debug("Initialization complete")
        self.trigger(BombStateChanged(BombState.INITIALIZED))
        # TODO implement an actual solution generation system
        self.time_left = 300.0
        for module in self.modules:
            module.generate()
            self.trigger(ModuleStateChanged(module))

    def deinitialize(self):
        """Stops all running tasks for the bomb."""
        if self._state == BombState.DEINITIALIZED:
            raise RuntimeError("Bomb already deinitialized")
        for task in self._running_tasks:
            task.cancel()
        self._bus.remove_listener(BusMessage, self._receive_message)
        self._gpio.remove_listener(ModuleReadyChange, self._module_ready_change)
        self._state = BombState.DEINITIALIZED

    def create_task(self, task: Coroutine) -> Task:
        """Creates a task that will be cancelled when the bomb is deinitialized.

        Returns an ``asyncio.Task``. If you want to cancel this task yourself, pass it to ``Bomb.cancel_task``
        so that it can be removed from the bomb's task list.
        """
        task = create_task(log_errors(task))
        self._running_tasks.append(task)
        return task

    def cancel_task(self, task: Task):
        """Manually cancels a task that was added with ``Bomb.create_task``."""
        task.cancel()
        self._running_tasks.remove(task)

    def _module_ready_change(self, change: ModuleReadyChange):
        if self._state in (BombState.UNINITIALIZED, BombState.RESETTING):
            return
        if change.present:
            # TODO trigger hotswap initialization for the single module
            self.trigger(BombError(None, BombErrorLevel.WARNING,
                                   f"A module was added at {self.casing.location(change.location)} "
                                   f"after initialization started."))
        elif change.location != self._init_location and change.location not in self.modules_by_location:
            # TODO handle cases where a module becomes unready during initialization
            self.trigger(BombError(None, BombErrorLevel.WARNING,
                                   f"A module was removed at {self.casing.location(change.location)} "
                                   f"after initialization started."))

    def _init_fail(self, reason):
        self._state = BombState.INITIALIZATION_FAILED
        self.trigger(BombError(None, BombErrorLevel.INIT_FAILURE, reason))

    async def _receive_message(self, message: BusMessage):
        async with self._state_lock:
            if self._state in (BombState.UNINITIALIZED, BombState.RESETTING, BombState.DEINITIALIZED):
                return
            if isinstance(message, AnnounceMessage):
                if self._state != BombState.INITIALIZING:
                    # TODO implement module hotswap
                    self.trigger(BombError(None, BombErrorLevel.WARNING,
                                           f"{message.module} was announced after initialization."))
                    return
                if message.module in self.modules_by_bus_id:
                    self._init_fail(f"Multiple modules were announced with id {message.module}.")
                    return
                if self._init_location is None:
                    self._init_fail(f"An unrequested announce was received from {message.module}.")
                    return
                module_class = MODULE_ID_REGISTRY[message.module.type]
                module = module_class(self, message.module, self._init_location, message.hw_version, message.sw_version)
                if message.init_complete:
                    module.state = ModuleState.CONFIGURATION
                self.modules_by_bus_id[message.module] = module
                self.modules_by_location[self._init_location] = module
                self.modules.append(module)
                self.trigger(BombModuleAdded(self, module))
                self._init_location = None
                self._init_cond.notify_all()
                return
            module = self.modules_by_bus_id.get(message.module)
            if module is None:
                self.trigger(BombError(None, BombErrorLevel.WARNING, f"Received {message.__class__.__name__} from "
                                                                     f"unannounced module {message.module}."))
                return
            module.last_received = monotonic()
            if not await module.handle_message(message):
                module.trigger_error(BombErrorLevel.WARNING, f"Received {message.__class__.__name__} in an "
                                                             f"invalid state.")

    async def send(self, message: BusMessage):
        """Sends a message to the bus."""
        # TODO check state maybe?
        await self._bus.send(message)

    async def _ping_loop(self):
        while True:
            for module in self.modules:
                await module.ping_check()
                # TODO module auto-restart?
            await async_sleep(0.1)

    def start_game(self):
        """Starts the game with the initial wait phase."""
        # TODO: prevent multiple instances from running
        self.create_task(self._start_game_task())

    async def _start_game_task(self):
        for module in self.modules:
            await module.send_state()
            module.state = ModuleState.GAME
        self._state = BombState.GAME_STARTING
        self.trigger(BombStateChanged(BombState.GAME_STARTING))
        await self.send(LaunchGameMessage(ModuleId.BROADCAST))
        # TODO: add at least an option to manually do the starting from UI
        await async_sleep(GAME_START_DELAY)
        if self._state != BombState.GAME_STARTING:
            return
        self._state = BombState.GAME_STARTED
        self.trigger(BombStateChanged(BombState.GAME_STARTED))
        await self.send(StartTimerMessage(ModuleId.BROADCAST))
        # timer task: trigger explosion and keep timer module in sync
        self._last_timer_update = monotonic()
        while self._state == BombState.GAME_STARTED:
            await self._update_time()
            expected_tick = (self.time_left % 1) / self.timer_speed
            await async_sleep(expected_tick)

    async def _update_time(self):
        now = monotonic()
        prev_second = int(self.time_left)
        self.time_left -= (now - self._last_timer_update) * self.timer_speed
        self.time_left = max(self.time_left, 0.0)
        self._last_timer_update = now
        curr_second = int(self.time_left)
        if self.time_left == 0.0:
            await self.explode()
            return
        if prev_second != curr_second:
            self.trigger(TimerTick(self))
            if self.timer_speed <= 1.0:
                self.sound_system.play_sound(TICK_SOUND_SLOW)
            elif self.timer_speed <= 1.25:
                self.sound_system.play_sound(TICK_SOUND_MEDIUM)
            else:
                self.sound_system.play_sound(TICK_SOUND_FAST)

    async def explode(self):
        """Ends the game by exploding the bomb."""
        self._state = BombState.EXPLODED
        self.trigger(BombStateChanged(BombState.EXPLODED))
        await self.send(ExplodeBombMessage(ModuleId.BROADCAST))
        self.sound_system.stop_all_sounds()
        self.sound_system.play_sound(EXPLOSION_SOUND)

    async def _handle_module_state_change(self, _: ModuleStateChanged):
        async with self._state_lock:
            if self._state == BombState.INITIALIZING and all(module.state == ModuleState.CONFIGURATION for module in self.modules):
                self._init_cond.notify_all()
                self._state = BombState.INITIALIZED
                return
            if self._state == BombState.GAME_STARTED and all(module.state == ModuleState.DEFUSED or not module.must_solve for module in self.modules):
                self._state = BombState.DEFUSED
                self.trigger(BombStateChanged(BombState.DEFUSED))
                await self.send(DefuseBombMessage(ModuleId.BROADCAST))

    async def strike(self, module: Module) -> bool:
        """Called by modules to indicate a strike.

        Returns ``True`` if the bomb exploded due to the strike, in which case the module should immediately stop
        sending messages to the bus.
        """
        self.strikes += 1
        if self.strikes >= self.max_strikes:
            await self.explode()
            return True
        if self.strikes <= 4:
            await self._update_time()
            self.timer_speed += 0.25
        self.trigger(ModuleStriked(module))
        self.sound_system.play_sound(STRIKE_SOUND)
        return False

    @property
    def timer_digits(self):
        # may not be perfectly synced with module when < 1 minute, but is close enough
        if self.time_left < 60:
            return f"{int(self.time_left):02d}{int(self.time_left % 1 * 100):02d}"
        return f"{int(self.time_left // 60):02d}{int(self.time_left % 60):02d}"


STRIKE_SOUND = register_sound(Bomb, "strike.wav", AudioLocation.BOMB_ONLY)
EXPLOSION_SOUND = register_sound(Bomb, "explosion.wav", AudioLocation.PREFER_ROOM)
TICK_SOUND_SLOW = register_sound(Bomb, "tick_1.0.wav", AudioLocation.BOMB_ONLY)
TICK_SOUND_MEDIUM = register_sound(Bomb, "tick_1.25.wav", AudioLocation.BOMB_ONLY)
TICK_SOUND_FAST = register_sound(Bomb, "tick_1.5.wav", AudioLocation.BOMB_ONLY)
