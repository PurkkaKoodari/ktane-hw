from __future__ import annotations

from abc import ABC
from asyncio import sleep as async_sleep
from enum import Enum
from random import random, randint

from bombgame.audio import register_sound, AudioLocation
from bombgame.bomb.state import BombState
from bombgame.bus.messages import NeedyActivateMessage, NeedyDeactivateMessage
from bombgame.events import BombStateChanged, ModuleStateChanged, ModuleStriked, ModuleDefused
from bombgame.modules.base import Module

NEEDY_ACTIVATION_CHANCE_ON_SOLVE = 0.85
NEEDY_ACTIVATION_DELAY_ON_SOLVE = 0.25
NEEDY_ACTIVATION_CHANCE_ON_STRIKE = 0.85
NEEDY_ACTIVATION_DELAY_ON_STRIKE = 0.75
NEEDY_INITIAL_DELAY = 90
NEEDY_REACTIVATION_DELAY = (10, 40)

NEEDY_DEFAULT_TIMER = 40
NEEDY_WARNING_START_TIME = 5
NEEDY_WARNING_REPEAT_TIME = 1.4


class NeedyState(Enum):
    INITIAL_SLEEP = 1
    SLEEPING = 2
    ACTIVATING = 3
    ACTIVE = 4
    DEACTIVATED = 5


class NeedyModule(Module, ABC):
    is_needy = True
    must_solve = False

    def __init__(self, bomb, bus_id, location, hw_version, sw_version):
        super().__init__(bomb, bus_id, location, hw_version, sw_version)
        self._needy_task = None
        self.needy_state = NeedyState.INITIAL_SLEEP
        self._needy_playing_sound = None
        bomb.add_listener(BombStateChanged, self._handle_bomb_state)
        bomb.add_listener(ModuleDefused, self._maybe_activate_on_solve)
        bomb.add_listener(ModuleStriked, self._maybe_activate_on_strike)

    def _handle_bomb_state(self, event: BombStateChanged):
        if event.state == BombState.GAME_STARTED:
            self._activate_with_delay(NEEDY_INITIAL_DELAY)
        elif event.state in (BombState.DEFUSED, BombState.EXPLODED):
            self._stop_activation()
            self.needy_state = NeedyState.DEACTIVATED
            self._bomb.trigger(ModuleStateChanged(self))

    def _activate_with_delay(self, duration: float):
        self._needy_task = self._bomb.create_task(self._sleep_and_activate(duration))

    async def _sleep_and_activate(self, duration: float):
        await async_sleep(duration)
        await self.activate()

    async def activate(self):
        self.needy_state = NeedyState.ACTIVE
        self._bomb.trigger(ModuleStateChanged(self))
        await self._bomb.send(NeedyActivateMessage(self.bus_id))
        self._bomb.sound_system.play_sound(NEEDY_ACTIVATE_SOUND)
        await self._play_needy_warning_loop()

    async def _play_needy_warning_loop(self, timer: float = NEEDY_DEFAULT_TIMER):
        await async_sleep(timer - NEEDY_WARNING_START_TIME)
        while True:
            self._needy_playing_sound = self._bomb.sound_system.play_sound(NEEDY_WARNING_SOUND)
            await async_sleep(NEEDY_WARNING_REPEAT_TIME)

    async def deactivate(self, *, permanently: bool = False):
        if self.needy_state == NeedyState.DEACTIVATED:
            return
        if not permanently and self.needy_state != NeedyState.ACTIVE:
            return
        self._stop_activation()
        if permanently:
            self.needy_state = NeedyState.DEACTIVATED
        else:
            self.needy_state = NeedyState.SLEEPING
            self._activate_with_delay(randint(*NEEDY_REACTIVATION_DELAY))
        self._bomb.trigger(ModuleStateChanged(self))
        await self._bomb.send(NeedyDeactivateMessage(self.bus_id))

    def _stop_activation(self):
        if self._needy_task:
            self._bomb.cancel_task(self._needy_task)
            self._needy_task = None
        if self._needy_playing_sound:
            self._needy_playing_sound.stop()

    async def needy_strike(self):
        if not await self.strike():
            await self.deactivate()

    def _maybe_activate_on_solve(self, _: ModuleDefused):
        if self.needy_state == NeedyState.INITIAL_SLEEP and random() < NEEDY_ACTIVATION_CHANCE_ON_SOLVE:
            self._stop_activation()
            self.needy_state = NeedyState.ACTIVATING
            self._activate_with_delay(NEEDY_ACTIVATION_DELAY_ON_SOLVE)

    def _maybe_activate_on_strike(self, _: ModuleStriked):
        if self.needy_state == NeedyState.INITIAL_SLEEP and random() < NEEDY_ACTIVATION_CHANCE_ON_STRIKE:
            self._stop_activation()
            self.needy_state = NeedyState.ACTIVATING
            self._activate_with_delay(NEEDY_ACTIVATION_DELAY_ON_STRIKE)


NEEDY_ACTIVATE_SOUND = register_sound(NeedyModule, "needy_activate.wav", AudioLocation.BOMB_ONLY)
NEEDY_WARNING_SOUND = register_sound(NeedyModule, "needy_warning.wav", AudioLocation.BOMB_ONLY)
