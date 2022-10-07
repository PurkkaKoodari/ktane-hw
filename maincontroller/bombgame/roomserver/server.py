import json
from asyncio import create_task, wait_for, TimeoutError as AsyncTimeoutError
from logging import getLogger
from typing import Optional, Union

from websockets import WebSocketServerProtocol, ConnectionClosed

from bombgame.audio import RoomServerSoundSystem
from bombgame.config import (ROOM_SERVER_PORT, ROOM_SERVER_AUTH_TIMEOUT, ROOM_SERVER_AUTH_KEY, ROOM_AUDIO_ENABLED,
                             ROOM_DMX_ENABLED)
from bombgame.dmx import initialize_local_dmx_backend, DMXBackend
from bombgame.roomserver.common import (ROOM_SERVER_VERSION, RoomServerChannel, parse_room_server_message,
                                        MessageHandlers)
from bombgame.utils import log_errors
from bombgame.websocket import SingleClientWebSocketServer, close_client_invalid_message, InvalidMessage

LOGGER = getLogger("RoomServer")


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
            return
        try:
            channel, data = parse_room_server_message(message)
        except InvalidMessage as ex:
            await close_client_invalid_message(client, ex.reason)
            return
        if channel != RoomServerChannel.AUTH:
            await close_client_invalid_message(client, "must send auth message upon connecting")
        if data.get("version") != ROOM_SERVER_VERSION:
            await close_client_invalid_message(client, "room server version mismatch", 4001)
        if data.get("key") != ROOM_SERVER_AUTH_KEY:  # TODO challenge-response
            await close_client_invalid_message(client, "auth key is incorrect", 4003)
        await self.send(RoomServerChannel.AUTH, {
            "ok": True,
        }, client)

    async def _handle_message(self, client: WebSocketServerProtocol, data: Union[str, bytes]):
        LOGGER.debug(str(data))
        await self._handle(data)

    async def send(self, channel: RoomServerChannel, payload: dict, client: Optional[WebSocketServerProtocol] = None):
        try:
            await self._send_to_client(json.dumps({
                "type": channel.value,
                "data": payload,
            }), client)
        except ConnectionClosed:
            pass  # will print the error in receiver if necessary

    def send_async(self, channel: RoomServerChannel, payload: dict):
        create_task(log_errors(self.send(channel, payload)))

    async def start(self):
        LOGGER.info("Starting room server")
        await self.start_server(ROOM_SERVER_PORT)
        if ROOM_AUDIO_ENABLED:
            self.sound_system = RoomServerSoundSystem(self)
            await self.sound_system.start()
        if ROOM_DMX_ENABLED:
            self.dmx = initialize_local_dmx_backend()
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
