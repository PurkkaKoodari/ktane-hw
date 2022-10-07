import json
from enum import Enum
from json.decoder import JSONDecodeError
from logging import getLogger
from typing import Union, Tuple, Callable, Coroutine, Dict

from bombgame.websocket import InvalidMessage

LOGGER = getLogger("RoomServer")

# compared against the string sent by the client to identify outdated servers
ROOM_SERVER_VERSION = "0.1-a2"


class RoomServerChannel(Enum):
    AUTH = "auth"
    DMX = "dmx"
    AUDIO = "audio"
    MUSIC = "music"
    WEB_UI = "web_ui"


# TODO: message parsing similar to WebInterface
def parse_room_server_message(data: Union[str, bytes]) -> Tuple[RoomServerChannel, dict]:
    if not isinstance(data, str):
        raise InvalidMessage("only text messages are valid")
    try:
        message = json.loads(data)
    except JSONDecodeError:
        raise InvalidMessage(f"invalid JSON message")
    if not isinstance(message, dict):
        raise InvalidMessage("invalid JSON message")

    try:
        channel = RoomServerChannel(message["type"])
    except (KeyError, ValueError):
        raise InvalidMessage("invalid channel") from None

    data = message.get("data")
    if not isinstance(data, dict):
        raise InvalidMessage("invalid data") from None

    return channel, data


class MessageHandlers:
    Handler = Callable[[dict], Coroutine]

    _handlers: Dict[RoomServerChannel, Handler]

    def __init__(self):
        self._handlers = {}

    def add_handler(self, channel: RoomServerChannel, handler: Handler):
        if channel in self._handlers:
            raise RuntimeError(f"handler for {channel.name} already registered")
        self._handlers[channel] = handler

    async def _handle(self, message: Union[str, bytes]):
        try:
            channel, data = parse_room_server_message(message)
            if channel in self._handlers:
                await self._handlers[channel](data)
            else:
                LOGGER.warning("Unexpected channel %s message to/from room server", channel.name)
        except InvalidMessage as ex:
            LOGGER.warning("Invalid message to/from room server: %s", ex.reason)
        except Exception:
            LOGGER.error("Error handling room server message", exc_info=True)
