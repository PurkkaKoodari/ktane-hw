import json
from asyncio import create_task, run, wait_for, TimeoutError as AsyncTimeoutError
from enum import Enum
from json import JSONDecodeError
from logging import getLogger
from sys import argv
from typing import Optional, Union, Tuple, Dict, Callable

from websockets import connect, WebSocketServerProtocol, ConnectionClosed, WebSocketClientProtocol

from bombgame.audio import RoomServerSoundSystem
from bombgame.config import (ROOM_SERVER, ROOM_SERVER_PORT, ROOM_SERVER_AUTH_TIMEOUT, ROOM_SERVER_AUTH_KEY,
                             ROOM_AUDIO_ENABLED, ROOM_DMX_ENABLED)
from bombgame.dmx import initialize_local_dmx_backend, DMXBackend
from bombgame.logging import init_logging
from bombgame.utils import log_errors, handle_sigint
from bombgame.websocket import SingleClientWebSocketServer, close_client_invalid_message, InvalidMessage

LOGGER = getLogger("RoomServer")

# compared against the string sent by the client to identify outdated servers
ROOM_SERVER_VERSION = "0.1-a1"


class RoomServerChannel(Enum):
    AUTH = "auth"
    DMX = "dmx"
    AUDIO = "audio"
    WEB_UI = "web_ui"


# TODO: message parsing similar to WebInterface
def _parse_message(data: Union[str, bytes]) -> Tuple[RoomServerChannel, dict]:
    if not isinstance(data, str):
        raise InvalidMessage("only text messages are valid")
    try:
        message = json.loads(data)
    except JSONDecodeError:
        raise InvalidMessage("invalid JSON message")
    if not isinstance(data, dict):
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
    Handler = Callable[[dict], None]

    _handlers: Dict[RoomServerChannel, Handler]

    def __init__(self):
        self._handlers = {}

    def add_handler(self, channel: RoomServerChannel, handler: Handler):
        if channel in self._handlers:
            raise RuntimeError(f"handler for {channel.name} already registered")
        self._handlers[channel] = handler

    async def _handle(self, message: Union[str, bytes]):
        try:
            channel, data = _parse_message(message)
            if channel in self._handlers:
                self._handlers[channel](data)
            else:
                LOGGER.warning("Unexpected channel %s message to/from room server", channel.name)
        except InvalidMessage as ex:
            LOGGER.warning("Invalid message to/from room server: %s", ex.reason)
        except Exception:
            LOGGER.error("Error handling room server message", exc_info=True)


class RoomServer(SingleClientWebSocketServer, MessageHandlers):
    sound_system: Optional[RoomServerSoundSystem]
    dmx: Optional[DMXBackend]

    def __init__(self):
        SingleClientWebSocketServer.__init__(self)
        MessageHandlers.__init__(self)
        self.sound_system = None
        self.dmx = None

    async def _new_client_connected(self, client: WebSocketServerProtocol):
        try:
            message = await wait_for(client.recv(), ROOM_SERVER_AUTH_TIMEOUT)
        except AsyncTimeoutError:
            await close_client_invalid_message(client, "must send auth message upon connecting")
        try:
            channel, data = _parse_message(message)
        except InvalidMessage as ex:
            await close_client_invalid_message(client, ex.reason)
        if channel != RoomServerChannel.AUTH:
            await close_client_invalid_message(client, "must send auth message upon connecting")
        if data.get("version") != ROOM_SERVER_VERSION:
            await close_client_invalid_message(client, "room server version mismatch", 4001)
        if data.get("key") != ROOM_SERVER_AUTH_KEY:  # TODO challenge-response
            await close_client_invalid_message(client, "auth key is incorrect", 4003)

        await self.send(RoomServerChannel.AUTH, {
            "ok": True,
        })

    async def _handle_message(self, client: WebSocketServerProtocol, data: Union[str, bytes]):
        await self._handle(data)

    async def send(self, channel: RoomServerChannel, payload: dict):
        try:
            await self._send_to_client(json.dumps({
                "type": channel.value,
                "data": payload,
            }))
        except ConnectionClosed:
            pass  # will print the error in receiver if necessary

    def send_async(self, channel: RoomServerChannel, payload: dict):
        create_task(log_errors(self.send(channel, payload)))

    async def start(self):
        LOGGER.info("Starting room server")
        await self.start_server(ROOM_SERVER_PORT)
        if ROOM_AUDIO_ENABLED:
            self.sound_system = RoomServerSoundSystem(self)
            self.sound_system.start()
        if ROOM_DMX_ENABLED:
            self.dmx = await initialize_local_dmx_backend()
            if self.dmx is not None:
                await self.dmx.start()
                self.dmx.add_room_server_handler(self)

    async def stop(self):
        if self.sound_system is not None:
            self.sound_system.stop()  # TODO: wrap in executor?
        if self.dmx is not None:
            await self.dmx.stop()
        LOGGER.info("Stopping room server")
        await self.stop_server()


class RoomServerClient(MessageHandlers):
    _connection: Optional[WebSocketClientProtocol]
    _close_requested: bool

    def __init__(self):
        super().__init__()
        self._connection = None
        self._close_requested = False

    async def start(self):
        if self._close_requested or self._connection is not None:
            raise RuntimeError("already started or stopped")
        LOGGER.info("Connecting to room server")
        self._connection = await connect(ROOM_SERVER)
        try:
            await self.send(RoomServerChannel.AUTH, {
                "version": ROOM_SERVER_VERSION,
                "key": ROOM_SERVER_AUTH_KEY,  # TODO challenge-response
            }, raise_errors=True)

            channel, data = _parse_message(await self._connection.recv())
            if channel != RoomServerChannel.AUTH or not data.get("ok"):
                raise InvalidMessage("expected to receive auth ok message")
        except (ConnectionClosed, InvalidMessage) as ex:
            raise RuntimeError(f"Failed to connect to room server: {type(ex).__name__}: {ex}")
        # TODO authenticate with server
        create_task(log_errors(self._background()))

    async def stop(self):
        self._close_requested = True
        if self._connection is not None:
            LOGGER.info("Closing room server connection")
            await self._connection.close()
            self._connection = None

    async def _background(self):
        try:
            async for message in self._connection:
                await self._handle(message)
        except ConnectionClosed as ex:
            if not self._close_requested:
                LOGGER.error("Room server connection closed unexpectedly (code %s)", ex.code, ex.reason)
        finally:
            self._connection = None

    async def send(self, channel: RoomServerChannel, payload: dict, raise_errors: bool = False):
        try:
            if self._connection:
                await self._connection.send(json.dumps({
                    "type": channel.value,
                    "data": payload,
                }))
        except ConnectionClosed:
            # will print the error in _background if necessary
            if raise_errors:
                raise

    def send_async(self, channel: RoomServerChannel, payload: dict):
        create_task(log_errors(self.send(channel, payload)))


async def main():
    verbose = "-v" in argv
    init_logging(verbose)
    LOGGER.info("Starting. Exit cleanly with SIGINT/Ctrl-C")
    quit_evt = handle_sigint()
    server = RoomServer()
    await server.start()
    await quit_evt.wait()
    await server.stop()
    LOGGER.info("Exiting")


if __name__ == "__main__":
    run(main())
