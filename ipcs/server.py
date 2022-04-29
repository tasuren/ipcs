# Ipcs - Server

from __future__ import annotations

from typing import Optional

from dataclasses import dataclass
from traceback import format_exc
from logging import getLogger
import asyncio

from websockets.server import serve, WebSocketServerProtocol
from websockets.exceptions import ConnectionClosed

from orjson import loads, dumps

from .types_ import Payload, ResponsePayload, Identifier
from .base import IpcsClientBase
from .client import IpcsClient
from .utils import _data_str


__all__ = ("Connection", "IpcsServer", "logger")
logger = getLogger("ipcs.server")
"Logger of ``logging`` in the standard library.\nName: ``ipcs.server``"


@dataclass
class Connection:
    "Data class for storing WebSockets connecting to the server."

    id_: Identifier
    "ID to identify the connecting client"
    ws: WebSocketServerProtocol | None = None
    """WebSocket used for communication.
    For ``Connection`` to handle requests from clients to the server, this is ``None``."""
    task: asyncio.Task | None = None
    """Coroutine task for communication.
    For ``Connection`` to handle requests from clients to the server, this is ``None``."""

    async def _send_json(self, server: IpcsServer, data: Payload) -> None:
        data["target"] = self.id_
        if self.ws is None:
            server.on_receive(data)
        else:
            try:
                await self.ws.send(dumps(data))
            except ConnectionClosed:
                ...
        logger.info(">>> %s" % _data_str(data))
        server.call_event("on_send", data)

    def __str__(self) -> str:
        return f"<Connection id_={self.id_} ws={self.ws} task={self.task}>"


class IpcsServer(IpcsClientBase):
    """:class:`IpcClient` is the class of the server to which you can connect.
    If you are installing from pypi, you can easily do this from the console with ``ipcs-server``.
    The client makes a request to the client, and this server class relays that request.
    ipcs also supports requests from the client to the server.
    The ID of the server is ``__IPCS_SERVER__``."""

    connections: dict[Identifier, Connection]
    """A dictionary that stores the WebSocket and other information during the connection.
    This includes a ``Connection`` for the client to make a request to the server.
    For this ``Connection``, the ``ws`` attribute, etc. will be ``None``.
    See :class:`Connection` for details.
    Note that the ID of the server is ``__IPCS_SERVER__``."""

    _close: Optional[asyncio.Future] = None
    _logger = logger

    def __init__(self, timeout: float = 8.0):
        self.connections = {"__IPCS_SERVER__": Connection("__IPCS_SERVER__")}

        super().__init__("__IPCS_SERVER__", timeout)

    async def send_json(self, data: Payload):
        if data["target"] in self.connections:
            await self.connections[data["target"]]._send_json(self, data)
        else:
            logger.warning("The data was sent to me, but there was no place to send it: %s" % _data_str(data))

    def is_ws_closed(self, ws: WebSocketServerProtocol) -> bool:
        """Check because WebSocket is finished.

        Args:
            ws: WebSocket"""
        return ws.closed

    async def _communicate(self, connection: Connection):
        # クライアントから送られて来たデータを、他のクライアントに送る。
        assert connection.ws is not None
        try:
            while not self.is_ws_closed(connection.ws):
                data: Payload = loads(await connection.ws.recv()) # type: ignore

                asyncio.create_task(
                    self.send_json(data),
                    name="ipc.server.send: %s" % connection
                )
                logger.info(f"<<< {_data_str(data)}")
                self.call_event("on_receive", data)
        except ConnectionClosed as e:
            IpcsClient._dis_warn(e, logger)
        except Exception as e:
            logger.error(f"Ignoring error on communication:\n{format_exc()}")

    async def communicate(self, ws: WebSocketServerProtocol) -> None:
        """Communicate with the passed WebSocket.
        This function is called from within :meth:`.start`.

        Args:
            ws: WebSocket"""
        logger.info(f"New websocket: {ws}")
        try:
            await ws.send("Ok?")
            id_ = await ws.recv()
            assert isinstance(id_, str)
            if id_ in self.connections:
                await ws.send("That ID is already in use.")
                await ws.close(1011, "That ID is already in use.")
                await ws.recv()
                return
            else:
                self.connections[id_] = Connection(id_, ws, None) # type: ignore
                self.connections[id_].task = asyncio.create_task(
                    self._communicate(self.connections[id_]),
                    name=f"ipc-server-communicate: {self.connections[id_]}"
                )
                logger.info(f"Registered websocket: {id_}")

                await ws.send("1") # 検証成功メッセージを送る。

                # クライアントにid追加を通知する。
                await self._send_all(ResponsePayload(
                    type="response", source="__IPCS_SERVER__", target="",
                    session="__IPCS_SERVER__", status="Special", data=(
                        "add_id", id_
                    )
                ))
                await self.connections[id_]._send_json(self, ResponsePayload(
                    type="response", source="__IPCS_SERVER__", target=id_,
                    session="__IPCS_SERVER__", status="Special", data=(
                        "update_ids", list(self.connections.keys())
                    )
                ))
        except ConnectionClosed as e:
            IpcsClient._dis_warn(e, logger)
            return

        # 接続終了まで待機する。
        self.call_event("on_connect", self.connections[id_])
        await self.connections[id_].task # type: ignore

        try:
            # クライアントにid削除を通知する。
            await self._send_all(ResponsePayload(
                type="response", source="__IPCS_SERVER__", target="",
                session="__IPCS_SERVER__", status="Special", data=(
                    "remove_id", id_
                )
            ))
        except ConnectionClosed as e:
            IpcsClient._dis_warn(e, logger)

        self.call_event("on_disconnect", self.connections[id_])
        del self.connections[id_]

    async def _send_all(self, data):
        await asyncio.gather(*(
            self.connections[id_]._send_json(self, data.copy())
            for id_ in self.connections.keys()
            if id_ != "__IPCS_SERVER__"
        ))

    async def start(self, **kwargs) -> None:
        """Run :meth:`.serve`.
        It also calls :meth:`.close` with error handling.

        Args:
            **kwargs: Keyword argument passed to :meth:`serve`."""
        logger.info("Start server")
        self.call_event("on_ready")
        try:
            await self.serve(**kwargs)
        except Exception as e:
            await self.close()
            raise e
        await self.close()

    async def serve(self, **kwargs) -> None:
        """Run the server by using ``websockets``.

        Args:
            **kwargs: Keyword argument passed to ``websockets.server.serve``."""
        self._close = asyncio.Future()
        async with serve(self.communicate, **kwargs):
            await self._close

    async def close(self, code: int = 1000, reason: str = "") -> None:
        """Disconnects from all connected clients.

        Args:
            code: The code for disconnection.
            reason: The reason for disconnection."""
        self.call_event("on_close")
        logger.info("Closing all connections...")
        for key, connection in list(self.connections.items()):
            if connection.ws is not None:
                await connection.ws.close(code, reason)
                del self.connections[key]
                logger.info("[%s] Closed" % key)
        if self._close is not None:
            self._close.set_result(None)
        logger.info("Closed")

    def run(self, **kwargs) -> None:
        """Run :meth:`.start`.

        Args:
            **kwargs: Keyword argument passed to :meth:`start`."""
        try:
            asyncio.run(self.start(**kwargs))
        except KeyboardInterrupt:
            ...