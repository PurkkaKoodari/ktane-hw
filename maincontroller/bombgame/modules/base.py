from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from logging import getLogger
from time import monotonic
from typing import Tuple, List, TYPE_CHECKING

from bombgame.bus.messages import (StrikeModuleMessage, SolveModuleMessage, ModuleId, ErrorMessage,
                                   RecoveredErrorMessage, PingMessage, BusMessage, InitCompleteMessage)
from bombgame.config import MODULE_PING_INTERVAL, MODULE_PING_TIMEOUT
from bombgame.events import BombError, BombErrorLevel, ModuleStateChanged
from bombgame.utils import VersionNumber

if TYPE_CHECKING:
    from bombgame.bomb.bomb import Bomb

PING_LOGGER = getLogger("ModulePing")

DEFAULT_ERROR_DESCRIPTIONS = {
    0: "The module received an invalid message.",
    1: "The module encountered an unknown hardware error.",
    2: "The module encountered an unknown software error."
}

UNKNOWN_ERROR_DESCRIPTION = "The module encountered an unknown error."


class ModuleState(Enum):
    INITIALIZATION = 1
    CONFIGURATION = 2
    GAME = 3
    DEFUSED = 4


class Module(ABC):
    """The base class for modules."""

    is_needy = False
    is_boss = False
    must_solve = True

    errors: List[Tuple[int, BombError]]

    _bomb: Bomb

    def __init__(self, bomb: Bomb, bus_id: ModuleId, location: int,
                 hw_version: VersionNumber, sw_version: VersionNumber):
        self._bomb = bomb
        self.bus_id = bus_id
        self.location = location
        self.hw_version = hw_version
        self.sw_version = sw_version
        self.last_received = monotonic()
        self.last_ping_time = None
        self.last_ping_id = 0
        self.ping_timeout = False
        self.state = ModuleState.INITIALIZATION
        self.errors = []

    def trigger_error(self, level: BombErrorLevel, message: str, code: int = -1):
        """Adds an error to this module and triggers an error event on the bomb."""
        error = BombError(self, level, message)
        self.errors.append((code, error))
        self._bomb.trigger(error)

    def _describe_error(self, error: ErrorMessage) -> str:
        """Generates a textual description of the given error."""
        try:
            return DEFAULT_ERROR_DESCRIPTIONS[error.code]
        except KeyError:
            return UNKNOWN_ERROR_DESCRIPTION

    async def ping_check(self) -> bool:
        """Checks if the module should trigger a ping timeout or send a ping. Returns ``False`` if a ping timeout
        occurred, ``True`` otherwise.
        """
        now = monotonic()
        if not self.ping_timeout and self.last_ping_time is not None and now > self.last_ping_time + MODULE_PING_TIMEOUT:
            PING_LOGGER.warning("%s didn't respond to ping id %d.", self, self.last_ping_id)
            self.ping_timeout = True
            self.trigger_error(BombErrorLevel.WARNING, "Ping timeout.")
            return False
        if self.last_ping_time is None and now > self.last_received + MODULE_PING_INTERVAL:
            self.last_ping_time = monotonic()
            self.last_ping_id = (self.last_ping_id + 1) & 0xFF
            PING_LOGGER.debug("Sending ping id %d to %s.", self.last_ping_id, self)
            await self._bomb.send(PingMessage(self.bus_id, number=self.last_ping_id))
        return True

    async def handle_message(self, message: BusMessage):
        """Handles an incoming message from the module. Returns ``True`` if the message was handled and the module was
        in a valid state to receive it, ``False`` if the message was invalid for the current state or unknown.

        Module classes should override this method to handle module-specific messages. For these, the subclass method
        should just return ``True``.

        If the module class requires custom handling for init completion or errors, it should process the messages and
        then call the base class method to ensure the class state gets updated.

        For any unhandled messages just call the base class method.
        """
        if isinstance(message, InitCompleteMessage) and self.state == ModuleState.INITIALIZATION:
            self.state = ModuleState.CONFIGURATION
            self._bomb.trigger(ModuleStateChanged(self))
            return True
        if isinstance(message, PingMessage):
            if self.last_ping_time is not None and self.last_ping_id == message.number:
                PING_LOGGER.debug("%s responded to ping id %d in %dms.",
                                  self, self.last_ping_id, (monotonic() - self.last_ping_time) * 1000)
                self.last_ping_time = None
            return True
        if isinstance(message, ErrorMessage):
            if isinstance(message, RecoveredErrorMessage):
                for code, existing in self.errors:
                    if code == message.code:
                        self.errors.remove((code, existing))
            self.trigger_error(message.error_level, self._describe_error(message), message.code)
            return True
        return False

    @abstractmethod
    def ui_state(self):
        """Returns a JSON-encodable object that represents the module's state to be passed to the UI."""

    @property
    def error_level(self) -> BombErrorLevel:
        """Returns the module's error level shown in the UI."""
        return max((error.level for _, error in self.errors), default=BombErrorLevel.NONE)

    @abstractmethod
    def generate(self):
        """Generates a state for the module."""
        # TODO: Figure out how this method is going to be used with different kinds of modules.
        #  For example, we might want to have a generic UI toolkit for modules to define a 'randomize'
        #  button on the web UI, but also allow manual input of e.g. wire colors

    @abstractmethod
    async def send_state(self):
        """Called by the bomb to send the state to a module that has been reset (including at game start)."""

    async def defuse(self):
        """Called by module code to mark the module as defused."""
        self.state = ModuleState.DEFUSED
        self._bomb.trigger(ModuleStateChanged(self))
        await self._bomb.send(SolveModuleMessage(self.bus_id))

    async def strike(self, count=True):
        """Called by module code to record a strike on the module."""
        if count:
            if await self._bomb.strike(self):
                return True
            await self._bomb.send(StrikeModuleMessage(self.bus_id))
            return False

    def __repr__(self):
        return f"<{self.__class__.__name__} serial {self.bus_id.serial} hw {self.hw_version} sw {self.sw_version} at {self._bomb.casing.location(self.location)}>"


class NeedyModule(Module, ABC):
    is_needy = True
    must_solve = False
