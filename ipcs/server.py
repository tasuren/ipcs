# Ipcs - Server

from __future__ import annotations

from typing import Optional

from dataclasses import dataclass
from traceback import format_exc
from logging import getLogger
from random import choice
from uuid import uuid4
import asyncio

from websockets.server import serve, WebSocketServerProtocol
from websockets.exceptions import ConnectionClosed

from ujson import loads, dumps

from .types_ import Payload, ResponsePayload, Identifier, AutoDecideRouteType
from .utils import EventManager, _data_str


__all__ = ("Connection", "IpcsServer", "logger")
logger = getLogger("ipcs.server")
"Logger of ``logging`` in the standard library.\nName: ``ipcs.server``"


@dataclass
class Connection:
    "Data class for storing WebSockets connecting to the server."

    uuid: Identifier
    ws: WebSocketServerProtocol
    task: asyncio.Task

    async def _send_json(self, server: IpcsServer, data: Payload) -> None:
        original = self.uuid
        if data["target"] == "ALL":
            original = "ALL"
        data["target"] = self.uuid
        logger.info(">>> %s" % _data_str(data))
        data["target"] = original
        server.call_event("on_send", data)
        try:
            await self.ws.send(dumps(data, ensure_ascii=False))
        except ConnectionClosed as e:
            logger.warn("It was disconnected for some reason: %s" % e)

    def __str__(self) -> str:
        return f"<Connection uuid={self.uuid} ws={self.ws} task={self.task}>"


class IpcsServer(EventManager):
    """:class:`IpcClient` is the class of server that can be connected to.
    If you are installing from pypi, you can easily do this from the console."""

    connections: dict[Identifier, Connection]
    "A dictionary that stores the WebSocket and other information during the connection."
    auto_decide_route_type: AutoDecideRouteType
    "The type of how to determine which client to send the request to when no request destination is specified."

    _close: Optional[asyncio.Future] = None

    def __init__(self, auto_decide_route_type: AutoDecideRouteType = AutoDecideRouteType.RANDOM):
        self.auto_decide_route_type = auto_decide_route_type

        self.connections = {}

        super().__init__()

    async def _send(self, type_: AutoDecideRouteType | None, data: Payload, source: Identifier):
        keys: list[Identifier] = list(filter(lambda x: x != source, self.connections.keys()))

        # 送信先を探す。
        if type_ is None:
            if data["target"] is not None:
                keys = [data["target"]]
        elif keys:
            if type_ == AutoDecideRouteType.RANDOM:
                keys = [choice(keys)]

        if keys:
            await asyncio.gather(*(
                self.connections[key]._send_json(self, data)
                for key in keys
            ))
        else:
            logger.warn("The data was sent to me, but there was no place to send it: %s" % _data_str(data))

    async def _communicate(self, connection: Connection):
        # クライアントから送られて来たデータを、他のクライアントに送る。
        try:
            while not connection.ws.closed:
                data: Payload = loads(await connection.ws.recv()) # type: ignore
                logger.info(f"<<< {_data_str(data)}")
                self.call_event("on_receive", data)
                if data["target"] is None:
                    type_ = self.auto_decide_route_type
                elif hasattr(AutoDecideRouteType, data["target"]):
                    type_ = getattr(AutoDecideRouteType, data["target"])
                else:
                    type_ = None
                asyncio.create_task(
                    self._send(type_, data, connection.uuid),
                    name="ipc-server-reply: %s" % connection
                )
        except ConnectionClosed as e:
            logger.warn("It was disconnected for some reason: %s" % e)
            logger.debug(format_exc())
        except Exception as e:
            logger.error(f"Ignoring error on communication:\n{format_exc()}")

    async def communicate(self, ws: WebSocketServerProtocol) -> None:
        """Communicate with the passed WebSocket.
        This function is called from within :meth:`.start`.

        Args:
            ws: WebSocket"""
        logger.info(f"New websocket: {ws}")
        await ws.send("Ok?")
        assert await ws.recv() == "verify"
        uuid = str(uuid4())
        self.connections[uuid] = Connection(uuid, ws, None) # type: ignore
        self.connections[uuid].task = asyncio.create_task(
            self._communicate(self.connections[uuid]),
            name=f"ipc-server-communicate: {self.connections[uuid]}"
        )
        await ws.send(uuid)
        logger.info(f"Registered websocket: {uuid}")

        # クライアントにuuid追加を通知する。
        await self._send_all(ResponsePayload(
            type="response", source="0", target="",
            session="0", status="Special", data=(
                "add_uuid", uuid
            )
        ))
        await self.connections[uuid]._send_json(self, ResponsePayload(
            type="response", source="0", target=uuid,
            session="0", status="Special", data=(
                "update_uuids", list(self.connections.keys())
            )
        ))

        # 接続終了まで待機する。
        self.call_event("on_connect", self.connections[uuid])
        await self.connections[uuid].task

        # クライアントにuuid削除を通知する。
        await self._send_all(ResponsePayload(
            type="response", source="0", target="",
            session="0", status="Special", data=(
                "remove_uuid", uuid
            )
        ))

        self.call_event("on_disconnect", self.connections[uuid])
        del self.connections[uuid]

    async def _send_all(self, data):
        await asyncio.gather(*(
            self.connections[uuid]._send_json(self, data.copy())
            for uuid in self.connections.keys()
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