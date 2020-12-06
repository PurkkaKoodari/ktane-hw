from abc import ABC, abstractmethod
from logging import getLogger
from typing import Optional, Union, NoReturn

from websockets import serve, WebSocketServerProtocol, WebSocketServer, ConnectionClosed

LOGGER = getLogger("WebSocket")


class InvalidMessage(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


async def close_client_invalid_message(client: WebSocketServerProtocol, reason: str = "invalid message", code: int = 1003) -> NoReturn:
    await client.close(code, reason)
    raise ConnectionClosed(code, reason) from None


class SingleClientWebSocketServer(ABC):
    _server: Optional[WebSocketServer]
    _client: Optional[WebSocketServerProtocol]

    def __init__(self):
        self._server = None
        self._client = None

    async def _send_to_client(self, message: Union[str, bytes], client: Optional[WebSocketServerProtocol] = None):
        if client is None:
            client = self._client
        if client is not None:
            try:
                await client.send(message)
            except ConnectionClosed:
                pass

    @abstractmethod
    async def _new_client_connected(self, client: WebSocketServerProtocol):
        """Called when a new client has connected and authenticated, just before it is about to replace any old client."""

    @abstractmethod
    async def _handle_message(self, client: WebSocketServerProtocol, data: Union[str, bytes]):
        """Called when a message is received from the current client."""

    async def _handle_client(self, client: WebSocketServerProtocol, _path: str):
        LOGGER.info("Client connected from %s", client.remote_address)
        try:
            await self._new_client_connected(client)
        except ConnectionClosed:
            LOGGER.warning("Client %s disconnected during handshake", client.remote_address)
            return
        LOGGER.debug("Client %s completed handshake", client.remote_address)
        old_client = self._client
        self._client = client
        if old_client:
            LOGGER.debug("Disconnecting previous client %s", old_client.remote_address)
            await old_client.close(4000)
        try:
            while True:
                await self._handle_message(client, await client.recv())
        except ConnectionClosed:
            if client is self._client:
                self._client = None
            return

    async def start_server(self, port: int):
        if self._server is not None:
            raise RuntimeError("server is already running")
        self._server = await serve(self._handle_client, port=port)

    async def stop_server(self):
        if self._server is None:
            raise RuntimeError("server is not running")
        self._server.close()
        await self._server.wait_closed()
