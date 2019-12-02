from __future__ import annotations
from asyncio import sleep as async_sleep
from enum import IntEnum
from random import randint, choice
import struct

from .base import Module
from .registry import MODULE_ID_REGISTRY, MODULE_MESSAGE_ID_REGISTRY
from ..bus.messages import BusMessage, BusMessageId, ModuleId, BusMessageDirection
from ..bomb.serial import VOWELS
from ..bomb.state import BombState
from ..events import ModuleStateChanged, BombStateChanged


class SimonColor(IntEnum):
    NONE = 0
    BLUE = 1
    YELLOW = 2
    GREEN = 3
    RED = 4


SIMON_BLINK_INTERVAL = 1.0
SIMON_START_DELAY = 1.0
SIMON_REPEAT_DELAY = 3.0


@MODULE_ID_REGISTRY.register
class SimonSaysModule(Module):
    module_id = 5

    __slots__ = ("_sequence", "_length", "_pressed", "_send_task")

    def __init__(self, bomb, bus_id, location, hw_version, sw_version):
        super().__init__(bomb, bus_id, location, hw_version, sw_version)
        self._sequence = None
        self._length = 1
        self._pressed = []
        self._send_task = None
        bomb.bus.add_listener(SimonButtonPressMessage, self._handle_press)
        bomb.bus.add_listener(SimonButtonBlinkMessage, self._handle_blink)
        bomb.add_listener(BombStateChanged, self._handle_bomb_state)

    def generate(self):
        length = randint(3, 5)
        self._sequence = [choice(SimonColor.__members__) for _ in range(length)]

    async def send_state(self):
        pass

    def ui_state(self):
        return {
            "sequence": [color.name for color in self._sequence[:self._length]],
            "pressed": [color.name for color in self._pressed]
        }

    def _color_map(self):
        if self._bomb.serial.has(VOWELS):
            if self._bomb.strikes == 0:
                presses = (SimonColor.BLUE, SimonColor.RED, SimonColor.YELLOW, SimonColor.GREEN)
            elif self._bomb.strikes == 1:
                presses = (SimonColor.YELLOW, SimonColor.GREEN, SimonColor.BLUE, SimonColor.RED)
            else:
                presses = (SimonColor.GREEN, SimonColor.RED, SimonColor.YELLOW, SimonColor.BLUE)
        else:
            if self._bomb.strikes == 0:
                presses = (SimonColor.BLUE, SimonColor.YELLOW, SimonColor.GREEN, SimonColor.RED)
            elif self._bomb.strikes == 1:
                presses = (SimonColor.RED, SimonColor.BLUE, SimonColor.YELLOW, SimonColor.GREEN)
            else:
                presses = (SimonColor.YELLOW, SimonColor.GREEN, SimonColor.BLUE, SimonColor.RED)
        blinks = (SimonColor.RED, SimonColor.BLUE, SimonColor.GREEN, SimonColor.YELLOW)
        return dict(zip(blinks, presses))

    async def _handle_press(self, event: SimonButtonPressMessage):
        self._pressed.append(event.color)
        correct = self._color_map()[self._sequence][self._length - 1]
        if event.color != correct:
            self._pressed = []
            self._bomb.trigger(ModuleStateChanged(self))
            await self.strike()
            self._restart_display()
        elif self._length == len(self._sequence):
            await self.defuse()
        else:
            self._length += 1
            self._bomb.trigger(ModuleStateChanged(self))
            self._restart_display()

    def _handle_bomb_state(self, event: BombStateChanged):
        if event.state == BombState.GAME_STARTED:
            self._restart_display()
        elif event.state in (BombState.GAME_PAUSED, BombState.EXPLODED, BombState.DEFUSED):
            self._stop_display()

    def _stop_display(self):
        if self._send_task is not None:
            self._bomb.cancel_task(self._send_task)
            self._send_task = None

    def _restart_display(self):
        self._stop_display()
        self._send_task = self._bomb.create_task(self._send_sequence())

    async def _send_sequence(self):
        await self._bomb.bus.send(SimonButtonBlinkMessage(self.bus_id, color=SimonColor.NONE))
        await async_sleep(SIMON_START_DELAY)
        while True:
            for color in self._sequence:
                await self._bomb.bus.send(SimonButtonBlinkMessage(self.bus_id, color=color))
                # TODO play sound
                await async_sleep(SIMON_BLINK_INTERVAL)
            await async_sleep(SIMON_REPEAT_DELAY)


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


@MODULE_MESSAGE_ID_REGISTRY.register
class SimonButtonBlinkMessage(SimonColoredMessage):
    message_id = (SimonSaysModule, BusMessageId.MODULE_SPECIFIC_0)


@MODULE_MESSAGE_ID_REGISTRY.register
class SimonButtonPressMessage(SimonColoredMessage):
    message_id = (SimonSaysModule, BusMessageId.MODULE_SPECIFIC_1)
