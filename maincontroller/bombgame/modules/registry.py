from __future__ import annotations

from typing import Type, TYPE_CHECKING

from bombgame.utils import Registry

if TYPE_CHECKING:
    from bombgame.modules.base import Module
    from bombgame.bus.messages import BusMessage

MODULE_ID_REGISTRY: Registry[int, Type[Module]] = Registry("module_id")
MODULE_MESSAGE_ID_REGISTRY: Registry[int, Type[BusMessage]] = Registry("message_id")
