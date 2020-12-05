from __future__ import annotations

import struct
from asyncio import sleep as async_sleep
from enum import IntEnum
from logging import getLogger
from random import randint, choice

from bombgame.audio import register_sound, play_sound, AudioLocation
from bombgame.bomb.serial import VOWELS
from bombgame.bomb.state import BombState
from bombgame.bus.messages import BusMessage, BusMessageId, ModuleId, BusMessageDirection
from bombgame.events import ModuleStateChanged, BombStateChanged
from bombgame.modules.base import Module, ModuleState
from bombgame.modules.registry import MODULE_ID_REGISTRY, MODULE_MESSAGE_ID_REGISTRY

LOGGER = getLogger("SimonSays")


class SimonColor(IntEnum):
    NONE = 0
    BLUE = 1
    YELLOW = 2
    GREEN = 3
    RED = 4


MAPPING_FLASHED = [SimonColor.RED, SimonColor.BLUE, SimonColor.GREEN, SimonColor.YELLOW]

MAPPING_PRESSED = {
    (True, 0): (SimonColor.BLUE, SimonColor.RED, SimonColor.YELLOW, SimonColor.GREEN),
    (True, 1): (SimonColor.YELLOW, SimonColor.GREEN, SimonColor.BLUE, SimonColor.RED),
    (True, 2): (SimonColor.GREEN, SimonColor.RED, SimonColor.YELLOW, SimonColor.BLUE),
    (False, 0): (SimonColor.BLUE, SimonColor.YELLOW, SimonColor.GREEN, SimonColor.RED),
    (False, 1): (SimonColor.RED, SimonColor.BLUE, SimonColor.YELLOW, SimonColor.GREEN),
    (False, 2): (SimonColor.YELLOW, SimonColor.GREEN, SimonColor.BLUE, SimonColor.RED),
}

SIMON_BLINK_INTERVAL = 0.6
SIMON_INITIAL_DELAY = 2.0
SIMON_REPEAT_DELAY = 5.0


@MODULE_ID_REGISTRY.register
class SimonSaysModule(Module):
    module_id = 5

    def __init__(self, bomb, bus_id, location, hw_version, sw_version):
        super().__init__(bomb, bus_id, location, hw_version, sw_version)
        self._sequence = None
        self._length = 1
        self._pressed = []
        self._send_task = None
        self._interacted = False
        self._playing_sound = None
        bomb.add_listener(BombStateChanged, self._handle_bomb_state)

    def generate(self):
        length = randint(3, 5)
        self._sequence = [choice(MAPPING_FLASHED) for _ in range(length)]

    async def send_state(self):
        pass

    def ui_state(self):
        if self._sequence is None:
            return {}
        return {
            "sequence": [color.name for color in self._sequence[:self._length]],
            "pressed": [color.name for color in self._pressed]
        }

    def _color_map(self):
        vowels = self._bomb.edgework.serial_number.has(VOWELS)
        strikes = min(self._bomb.strikes, 2)
        return dict(zip(MAPPING_FLASHED, MAPPING_PRESSED[vowels, strikes]))

    async def _handle_press(self, pressed: SimonColor):
        if self.state == ModuleState.DEFUSED:
            LOGGER.info("Pressed %s when module was already solved", pressed.name)
            await self.strike()
            return

        self._interacted = True
        self._pressed.append(pressed)
        flashed = self._sequence[len(self._pressed) - 1]
        correct = self._color_map()[flashed]
        if pressed != correct:
            LOGGER.info("Pressed %s, expected %s (%s flashed)", pressed.name, correct.name, flashed.name)
            self._pressed.clear()
            self._bomb.trigger(ModuleStateChanged(self))
            if await self.strike():
                self._stop_display()
                return
            await self._blink_button(pressed)
            self._restart_display(SIMON_INITIAL_DELAY)
            return

        LOGGER.info("Pressed %s correctly", pressed.name)
        await self._blink_button(pressed)
        if len(self._pressed) < self._length:
            self._bomb.trigger(ModuleStateChanged(self))
            self._restart_display(SIMON_REPEAT_DELAY)
        elif self._length < len(self._sequence):
            self._length += 1
            self._pressed.clear()
            self._bomb.trigger(ModuleStateChanged(self))
            self._restart_display(SIMON_INITIAL_DELAY)
        else:
            await self.defuse()
            self._stop_display()

    async def handle_message(self, message: BusMessage):
        if isinstance(message, SimonButtonPressMessage) and self.state in (ModuleState.GAME, ModuleState.DEFUSED):
            await self._handle_press(message.color)
            return True
        return await super().handle_message(message)

    def _handle_bomb_state(self, event: BombStateChanged):
        if event.state == BombState.GAME_STARTED:
            self._restart_display(SIMON_INITIAL_DELAY)
        elif event.state in (BombState.GAME_PAUSED, BombState.EXPLODED, BombState.DEFUSED):
            self._stop_display()

    def _stop_display(self):
        if self._send_task is not None:
            self._bomb.cancel_task(self._send_task)
            self._send_task = None

    def _restart_display(self, delay: float):
        self._stop_display()
        self._send_task = self._bomb.create_task(self._send_sequence(delay))

    async def _send_sequence(self, delay: float):
        await async_sleep(delay)
        if self._pressed:
            self._pressed.clear()
            self._bomb.trigger(ModuleStateChanged(self))
        while True:
            for color in self._sequence[:self._length]:
                await self._blink_button(color)
                await async_sleep(SIMON_BLINK_INTERVAL)
            await async_sleep(SIMON_REPEAT_DELAY)

    async def _blink_button(self, color: SimonColor):
        await self._bomb.send(SimonButtonBlinkMessage(self.bus_id, color=color))
        if self._interacted:
            if self._playing_sound:
                self._playing_sound.stop()
            self._playing_sound = play_sound(SIMON_SOUNDS[color])


SIMON_SOUNDS = {
    SimonColor.RED: register_sound(SimonSaysModule, "simon_red.wav", AudioLocation.BOMB_ONLY),
    SimonColor.BLUE: register_sound(SimonSaysModule, "simon_blue.wav", AudioLocation.BOMB_ONLY),
    SimonColor.GREEN: register_sound(SimonSaysModule, "simon_green.wav", AudioLocation.BOMB_ONLY),
    SimonColor.YELLOW: register_sound(SimonSaysModule, "simon_yellow.wav", AudioLocation.BOMB_ONLY)
}


class SimonColoredMessage(BusMessage):
    __slots__ = ("color",)

    def __init__(self, module: ModuleId, direction: BusMessageDirection = BusMessageDirection.OUT, *,
                 color: SimonColor):
        super().__init__(self.__class__.message_id[1], module, direction)
        self.color = color

    @classmethod
    def _parse_data(cls, module: ModuleId, direction: BusMessageDirection, data: bytes):
        if len(data) != 1:
            raise ValueError(f"{cls.__name__} must have 1 byte of data")
        color, = struct.unpack("<B", data)
        return cls(module, direction, color=SimonColor(color))

    def _serialize_data(self):
        return struct.pack("<B", self.color)

    def _data_repr(self):
        return self.color.name


@MODULE_MESSAGE_ID_REGISTRY.register
class SimonButtonBlinkMessage(SimonColoredMessage):
    message_id = (SimonSaysModule, BusMessageId.MODULE_SPECIFIC_0)


@MODULE_MESSAGE_ID_REGISTRY.register
class SimonButtonPressMessage(SimonColoredMessage):
    message_id = (SimonSaysModule, BusMessageId.MODULE_SPECIFIC_1)
