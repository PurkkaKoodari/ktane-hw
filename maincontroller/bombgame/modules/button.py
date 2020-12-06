from __future__ import annotations

import struct
from enum import IntEnum, Enum
from random import choice
from typing import Optional, Tuple, List, Callable, Dict

from bombgame.bomb.edgework import IndicatorName, Edgework
from bombgame.bus.messages import BusMessage, BusMessageId, ModuleId, BusMessageDirection
from bombgame.events import ModuleStateChanged
from bombgame.modules.base import Module, ModuleState
from bombgame.modules.registry import MODULE_ID_REGISTRY, MODULE_MESSAGE_ID_REGISTRY


class ButtonAction(IntEnum):
    PRESS = 0
    HOLD = 1
    RELEASE_PRESS = 2
    RELEASE_HOLD = 3


class ButtonColor(IntEnum):
    BLUE = 0
    WHITE = 1
    RED = 2
    YELLOW = 3


class ButtonText(Enum):
    DETONATE = "DETONATE"
    PRESS = "PRESS"
    HOLD = "HOLD"
    ABORT = "ABORT"


class ButtonLightColor(Enum):
    BLUE = (0, 0, 255)
    WHITE = (255, 255, 255)
    YELLOW = (255, 255, 0)
    RED = (255, 0, 0)


RULES: List[Tuple[Callable[[Edgework, ButtonColor, ButtonText], bool], bool]] = [
    (lambda edgework, color, text: color == ButtonColor.BLUE and text == ButtonText.ABORT, True),
    (lambda edgework, color, text: edgework.batteries() > 1 and text == ButtonText.DETONATE, False),
    (lambda edgework, color, text: color == ButtonColor.WHITE and edgework.indicator(IndicatorName.CAR).lit, True),
    (lambda edgework, color, text: edgework.batteries() > 2 and edgework.indicator(IndicatorName.FRK).lit, False),
    (lambda edgework, color, text: color == ButtonColor.YELLOW, True),
    (lambda edgework, color, text: color == ButtonColor.RED and text == ButtonText.HOLD, False),
    (lambda edgework, color, text: True, True),
]

RELEASE_RULES: Dict[ButtonLightColor, str] = {
    ButtonLightColor.BLUE: "4",
    ButtonLightColor.WHITE: "1",
    ButtonLightColor.YELLOW: "5",
    ButtonLightColor.RED: "1",
}


@MODULE_ID_REGISTRY.register
class ButtonModule(Module):
    module_id = 3

    __slots__ = ("_button_color", "_button_text", "_light_color", "_should_hold", "_pressed", "_held",)

    _button_color: Optional[ButtonColor]
    _button_text: Optional[ButtonText]
    _light_color: Optional[ButtonLightColor]
    _should_hold: bool
    _pressed: bool
    _held: bool

    def __init__(self, bomb, bus_id, location, hw_version, sw_version):
        super().__init__(bomb, bus_id, location, hw_version, sw_version)
        self._button_color = None
        self._button_text = None
        self._should_hold = False
        self._pressed = False
        self._held = False

    def generate(self):
        self._button_color = choice(list(ButtonColor.__members__.values()))
        self._button_text = choice(list(ButtonText.__members__.values()))
        self._light_color = choice(list(ButtonLightColor.__members__.values()))
        for condition, should_hold in RULES:
            if condition(self._bomb.edgework, self._button_color, self._button_text):
                self._should_hold = should_hold
                break
        else:
            raise AssertionError("failed to generate solution")

    async def send_state(self):
        pass

    async def handle_message(self, message: BusMessage):
        if isinstance(message, ButtonActionMessage) and self.state in (ModuleState.GAME, ModuleState.DEFUSED):
            if message.action == ButtonAction.PRESS:
                self._pressed = True
                self._bomb.trigger(ModuleStateChanged(self))
            elif message.action == ButtonAction.HOLD:
                self._held = True
                if self._should_hold:
                    await self._bomb.send(ButtonLightMessage(self.bus_id, color=self._light_color.value))
                else:
                    await self.strike()
            elif message.action == ButtonAction.RELEASE_PRESS:
                self._pressed = False
                self._bomb.trigger(ModuleStateChanged(self))
                if not self._should_hold:
                    await self.defuse()
                else:
                    await self.strike()
            elif message.action == ButtonAction.RELEASE_HOLD:
                self._pressed = False
                self._held = False
                self._bomb.trigger(ModuleStateChanged(self))
                if self._should_hold:
                    await self._bomb.send(ButtonLightMessage(self.bus_id, color=(0, 0, 0)))
                    expected_digit = RELEASE_RULES[self._light_color]
                    if expected_digit in self._bomb.timer_digits:
                        await self.defuse()
                    else:
                        await self.strike()
            return True
        return await super().handle_message(message)

    def ui_state(self):
        if self._button_color is None:
            return {}
        return {
            "color": self._button_color.name,
            "text": self._button_text.name,
            "should_hold": self._should_hold,
            "light_color": self._light_color.name,
            "pressed": self._pressed,
        }


@MODULE_MESSAGE_ID_REGISTRY.register
class ButtonActionMessage(BusMessage):
    message_id = (ButtonModule, BusMessageId.MODULE_SPECIFIC_0)

    __slots__ = ("action",)

    def __init__(self, module: ModuleId, direction: BusMessageDirection = BusMessageDirection.OUT, *,
                 action: ButtonAction):
        super().__init__(self.__class__.message_id[1], module, direction)
        self.action = action

    @classmethod
    def _parse_data(cls, module: ModuleId, direction: BusMessageDirection, data: bytes):
        if len(data) != 1:
            raise ValueError(f"{cls.__name__} must have 1 byte of data")
        action, = struct.unpack("<B", data)
        return cls(module, direction, action=ButtonAction(action))

    def _serialize_data(self):
        return struct.pack("<B", self.action.value)

    def _data_repr(self):
        return self.action.name


@MODULE_MESSAGE_ID_REGISTRY.register
class ButtonLightMessage(BusMessage):
    message_id = (ButtonModule, BusMessageId.MODULE_SPECIFIC_1)

    __slots__ = ("color",)

    def __init__(self, module: ModuleId, direction: BusMessageDirection = BusMessageDirection.OUT, *,
                 color: Tuple[int, int, int]):
        super().__init__(self.__class__.message_id[1], module, direction)
        if not all(0 <= val <= 255 for val in color):
            raise ValueError("color values must be 0-255")
        self.color = color

    @classmethod
    def _parse_data(cls, module: ModuleId, direction: BusMessageDirection, data: bytes):
        if len(data) != 3:
            raise ValueError(f"{cls.__name__} must have 3 bytes of data")
        color = struct.unpack("<3B", data)
        return cls(module, direction, color=color)

    def _serialize_data(self):
        return struct.pack("<3B", *self.color)

    def _data_repr(self):
        return f"{self.color}"
