import struct
from logging import getLogger
from random import randint, randrange, sample, choice
from typing import Callable, Dict, Tuple, Sequence

from bombgame.bomb.edgework import Edgework, PortType
from bombgame.bomb.serial import EVEN
from bombgame.bomb.state import BombState
from bombgame.bus.messages import BusMessageId, BusMessage, ModuleId, BusMessageDirection
from bombgame.events import BombStateChanged, BombError, BombErrorLevel, ModuleStateChanged
from bombgame.modules.base import Module, ModuleState, NoSolution
from bombgame.modules.registry import MODULE_ID_REGISTRY, MODULE_MESSAGE_ID_REGISTRY
from bombgame.modules.wires import WireColor, WiresUpdateMessage

LOGGER = getLogger("ComplicatedWires")

VALID_COLORS = (WireColor.WHITE, WireColor.RED, WireColor.BLUE, WireColor.RED_BLUE)
WIRE_MAPPING = {
    WireColor.BLACK: WireColor.WHITE,
    WireColor.YELLOW: WireColor.WHITE,
}

RuleCondition = Callable[[WireColor, bool, bool], bool]
RuleDecision = Callable[[Edgework], bool]

CONDITIONS: Tuple[RuleCondition, ...] = (
    lambda color, led, star: color in (WireColor.RED, WireColor.RED_BLUE),
    lambda color, led, star: color in (WireColor.BLUE, WireColor.RED_BLUE),
    lambda color, led, star: star,
    lambda color, led, star: led,
)

RULE_CUT: RuleDecision = lambda edgework: True
RULE_DONT_CUT: RuleDecision = lambda edgework: False
RULE_SERIAL_EVEN: RuleDecision = lambda edgework: edgework.serial_number.last_is(EVEN)
RULE_PARALLEL: RuleDecision = lambda edgework: edgework.ports(PortType.PARALLEL) > 0
RULE_BATTERIES: RuleDecision = lambda edgework: edgework.batteries() >= 2

RULES: Dict[Tuple[bool, ...], RuleDecision] = {
    (False, False, False, False): RULE_CUT,
    (True, False, False, False): RULE_SERIAL_EVEN,
    (False, True, False, False): RULE_SERIAL_EVEN,
    (True, True, False, False): RULE_SERIAL_EVEN,
    (False, False, True, False): RULE_CUT,
    (True, False, True, False): RULE_CUT,
    (False, True, True, False): RULE_DONT_CUT,
    (True, True, True, False): RULE_PARALLEL,
    (False, False, False, True): RULE_DONT_CUT,
    (True, False, False, True): RULE_BATTERIES,
    (False, True, False, True): RULE_PARALLEL,
    (True, True, False, True): RULE_DONT_CUT,
    (False, False, True, True): RULE_BATTERIES,
    (True, False, True, True): RULE_BATTERIES,
    (False, True, True, True): RULE_PARALLEL,
    (True, True, True, True): RULE_DONT_CUT,
}


def _compute_solution(edgework: Edgework, wires: Sequence[WireColor], leds: Sequence[bool], stars: Sequence[bool]):
    solution = [False] * 6
    for pos, wire in enumerate(wires):
        if wire != WireColor.DISCONNECTED:
            conds = tuple(cond(wire, leds[pos], stars[pos]) for cond in CONDITIONS)
            solution[pos] = RULES[conds](edgework)

    # a valid solution will have at least one wire to cut
    if True not in solution:
        raise NoSolution
    return solution


@MODULE_ID_REGISTRY.register
class ComplicatedWiresModule(Module):
    module_id = 9

    __slots__ = ("_initial_connected", "_leds", "_stars", "_connected", "_cut", "_solution")

    def __init__(self, bomb, bus_id, location, hw_version, sw_version):
        super().__init__(bomb, bus_id, location, hw_version, sw_version)
        self._initial_connected = [WireColor.DISCONNECTED] * 6
        self._leds = [False] * 6
        self._stars = [False] * 6
        self._connected = [WireColor.DISCONNECTED] * 6
        self._cut = [False] * 6
        self._solution = None
        bomb.add_listener(BombStateChanged, self._handle_bomb_state)

    def generate(self):
        while True:
            self._leds = [randrange(2) == 1 for _ in range(6)]
            self._stars = [randrange(2) == 1 for _ in range(6)]

            self._initial_connected = [WireColor.DISCONNECTED] * 6
            wire_count = randint(3, 6)  # TODO check the lower limit for this
            wire_positions = sample(range(6), wire_count)
            wire_colors = [choice(VALID_COLORS) for _ in range(wire_count)]
            for pos, color in zip(wire_positions, wire_colors):
                self._initial_connected[pos] = color

            try:
                self._solution = _compute_solution(self._bomb.edgework, self._initial_connected, self._leds, self._stars)
                break
            except NoSolution:
                pass

    async def send_state(self):
        await self._bomb.send(ComplicatedWiresSetLedsMessage(self.bus_id, leds=self._leds))

    def ui_state(self):
        if self._solution is None:
            return {}
        return {
            "wires": [wire.name for wire in self._initial_connected],
            "leds": self._leds,
            "stars": self._stars,
            "connected": [wire.name for wire in self._connected],
            "cut": self._cut,
            "solution": self._solution,
        }

    def _handle_bomb_state(self, event: BombStateChanged):
        if event.state == BombState.GAME_STARTING:
            mapped = [WIRE_MAPPING.get(color, color) for color in self._connected]
            bad_pos = [str(pos + 1) for pos in range(6) if self._initial_connected[pos] != mapped[pos]]
            if bad_pos:
                try:
                    new_solution = _compute_solution(self._bomb.edgework, self._connected, self._leds, self._stars)
                except NoSolution:
                    new_solution = None

                if new_solution == self._solution:
                    self._bomb.trigger(BombError(self, BombErrorLevel.MINOR,
                                                 f"The wires in positions {', '.join(bad_pos)} do not match the "
                                                 f"expected state, but the solution happens to be the same."))
                elif all(not cut or self._connected[pos] != WireColor.DISCONNECTED for pos, cut in enumerate(self._solution)):
                    positions = ' '.join(str(pos + 1) for pos, cut in enumerate(self._solution) if cut)
                    self._bomb.trigger(BombError(self, BombErrorLevel.MAJOR,
                                                 f"The wires in positions {', '.join(bad_pos)} do not match the "
                                                 f"expected state, but the module can still be defused by cutting the "
                                                 f"wires in positions {positions}."))
                else:
                    self._bomb.trigger(BombError(self, BombErrorLevel.MAJOR,
                                                 f"The wires in positions {', '.join(bad_pos)} do not match the "
                                                 f"expected state, making the module unsolvable."))

    async def handle_message(self, message: BusMessage):
        if isinstance(message, ComplicatedWiresUpdateMessage):
            prev_connected = self._connected
            self._connected = list(message.wires)
            if self.state == ModuleState.CONFIGURATION:
                try:
                    new_solution = _compute_solution(self._bomb.edgework, self._connected, self._leds, self._stars)
                except NoSolution:
                    pass
                else:
                    self._initial_connected = self._connected
                    self._solution = new_solution
            elif self.state in (ModuleState.GAME, ModuleState.DEFUSED):
                for pos in range(6):
                    # a wire is disconnected when it:
                    if (not self._cut[pos]  # hasn't been cut yet
                            and self._initial_connected[pos] != WireColor.DISCONNECTED  # is supposed to exist
                            and prev_connected[pos] != WireColor.DISCONNECTED  # did exist a moment ago
                            and self._connected[pos] == WireColor.DISCONNECTED):  # no longer exists
                        self._cut[pos] = True
                        if self._solution[pos]:
                            LOGGER.info("Wire %s cut correctly", pos + 1)
                            if all(has_cut or not should_cut for should_cut, has_cut in zip(self._solution, self._cut)):
                                await self.defuse()
                        else:
                            LOGGER.info("Wire %s cut incorrectly", pos + 1)
                            if await self.strike():
                                return
            self._bomb.trigger(ModuleStateChanged(self))
            return True
        return await super().handle_message(message)


@MODULE_MESSAGE_ID_REGISTRY.register
class ComplicatedWiresUpdateMessage(WiresUpdateMessage):
    message_id = (ComplicatedWiresModule, BusMessageId.MODULE_SPECIFIC_0)


@MODULE_MESSAGE_ID_REGISTRY.register
class ComplicatedWiresSetLedsMessage(BusMessage):
    message_id = (ComplicatedWiresModule, BusMessageId.MODULE_SPECIFIC_1)

    __slots__ = ("leds",)

    def __init__(self, module: ModuleId, direction: BusMessageDirection = BusMessageDirection.OUT, *,
                 leds: Sequence[bool]):
        super().__init__(self.__class__.message_id[1], module, direction)
        if len(leds) != 6:
            raise ValueError("must have 6 leds")
        self.leds = tuple(leds)

    @classmethod
    def _parse_data(cls, module: ModuleId, direction: BusMessageDirection, data: bytes):
        if len(data) != 1:
            raise ValueError(f"{cls.__name__} must have 1 byte of data")
        bitfield, = struct.unpack("<B", data)
        leds = [bool(bitfield & (1 << pos)) for pos in range(6)]
        return cls(module, direction, leds=leds)

    def _serialize_data(self):
        return struct.pack("<B", sum(val << pos for pos, val in enumerate(self.leds)))

    def _data_repr(self):
        return " ".join("ON" if val else "off" for val in self.leds)
