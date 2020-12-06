import json
from asyncio import create_task
from logging import getLogger
from typing import Optional

from websockets import WebSocketClientProtocol, connect, ConnectionClosed

from bombgame.config import ROOM_SERVER, ROOM_SERVER_AUTH_KEY
from bombgame.roomserver.common import (MessageHandlers, RoomServerChannel, ROOM_SERVER_VERSION,
                                        parse_room_server_message)
from bombgame.utils import log_errors
from bombgame.websocket import InvalidMessage

LOGGER = getLogger("RoomServer")


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

            channel, data = parse_room_server_message(await self._connection.recv())
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
