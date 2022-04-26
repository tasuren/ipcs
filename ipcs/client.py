# ipcs - Client

from __future__ import annotations

from typing import Optional

from logging import getLogger

import asyncio

from websockets.exceptions import ConnectionClosed
from websockets.client import WebSocketClientProtocol, connect

from orjson import dumps, loads

from .types_ import Identifier, Payload, ResponsePayload
from .base import IpcsClientBase
from .utils import _data_str
from . import exceptions


__all__ = ("IpcsClient", "logger")
logger = getLogger("ipcs.client")
"Logger of ``logging`` in the standard library.\nName: ``ipcs.client``"


class IpcsClient(IpcsClientBase):
    """IPC client to connect to :class:`IpcServer`.

    Args:
        id_: ID for client identification
        timeout: Seconds until request times out"""

    ws: Optional[WebSocketClientProtocol] = None
    "This should assigned an instance of the class used for websocket communication."
    connected: asyncio.Event
    "To record the status of the connection."
    ready: asyncio.Event
    "To record whether preparations have been completed"
    clients: list[Identifier]
    """List of id of clients connecting to the server.
    Since we allow requests to be made to the server, this will contain an ``__IPCS_SERVER__`` ID representing the server, even if no one is connected."""

    _logger = logger

    def __init__(self, *args, **kwargs):
        self.connected, self.ready = asyncio.Event, asyncio.Event
        self.clients = []
        super().__init__(*args, **kwargs)

    def check(self, target: Identifier) -> None:
        # もし送信先が不明の場合はエラーを起こす。
        if target not in self.clients:
            raise exceptions.TargetNotFound("No destination found: %s" % target)

    async def connect(self, reconnect: bool = True, **kwargs) -> None:
        """Connect to the server.

        Args:
            reconnect: Whether to reconnect
            **kwargs: The keyword arguments to be passed to :func:`websockets.client.connect`.

        Raises:
            VerifyFailed: Occurs when the client is not acknowledged by the server.
                One possible cause is that a client with the same ID has already connected to the server."""
        self._logger.info("Connecting...")
        async for ws in connect(**kwargs):
            self._logger.info("Connected")

            # 下準備をする。
            self.connected.set()
            self.call_event("on_connect")
            self.ws = ws
            self.response_waiters = {}

            # 実行する。
            try:
                self._logger.info("Verifying...")
                await asyncio.wait_for(self._verify(), timeout=self.timeout)
                self._logger.info("Verified: %s" % self.id_)

                self._receiver_task = asyncio.create_task(
                    self._receiver(), name="ipcs.client.reeciver"
                )
                self.ready.set()
                self.call_event("on_ready")
                await self._receiver_task
            except Exception as e:
                if isinstance(e, ConnectionClosed | asyncio.TimeoutError):
                    self.connected.clear()
                    self.ready.clear()
                    self.call_event("on_disconnect")
                    if reconnect:
                        self._dis_warn(e, self._logger)
                        await asyncio.sleep(3)
                        self._logger.info("Connecting...")
                        continue
                raise e

    def _when_special(self, data: ResponsePayload):
        # Specialなレスポンスの場合呼ばれる。
        if data["data"][0] == "call_event":
            self.call_event(*data["data"][1][0], **data["data"][1][1])
        elif data["data"][0] == "add_id":
            if data["data"][1] not in self.clients:
                if data["data"][1] != self.clients:
                    self.call_event("on_connect_at_server", data["data"][1])
                self.clients.append(data["data"][1])
        elif data["data"][0] == "remove_id":
            if data["data"][1] in self.clients:
                if data["data"][1] != self.id_:
                    self.call_event("on_disconnect_at_server", data["data"][1])
                self.clients.remove(data["data"][1])
        elif data["data"][0] == "update_ids":
            self.clients = data["data"][1]

    async def send_json(self, data: Payload) -> None:
        assert self.ws is not None
        self._logger.info(">>> %s" % _data_str(data))
        self.call_event("on_send", data)
        await self.ws.send(dumps(data))

    async def _receiver(self):
        # サーバーから送られてくるデータを受け取り適切な処理を行います。
        while True:
            self.on_receive(loads(await self.ws.recv()))

    async def _verify(self):
        # 自分のIDが使用可能か確認したりする。
        await self.ws.recv()
        await self.ws.send(self.id_)
        result = await self.ws.recv()
        if result != "1":
            raise exceptions.VerifyFailed(result)

    async def start(self, *args, **kwargs):
        """Connect to the server and post-process when end.

        Args:
            *args: The arguments to be passed to :meth:`.connect`.
            *kwargs: The keyword arguments to be passed to :meth:`.connect`."""
        try:
            await self.connect(*args, **kwargs)
        except Exception as e:
            await self.close(1011, "Error was occured: %s" % e)
            raise e
        else:
            await self.close()

    def run(self, *args, **kwargs):
        """Use :func:`asyncio.run` to run :meth:`.start`.

        Args:
            *args: The arguments to be passed to :meth:`.start`.
            *kwargs: The keyword arguments to be passed to :meth:`.start`."""
        try:
            asyncio.run(self.start(*args, **kwargs))
        except KeyboardInterrupt:
            ...

    async def close(self, code: int = 1000, reason: str = "") -> None:
        """If it is still connected, disconnect it and do the post-processing.

        Args:
            code: CloseCode
            reason: Reason of close"""
        self.call_event("on_close")
        if hasattr(self, "ws") and self.ws is not None:
            await self.ws.close(code, reason)
        if self.response_waiters and self.id_ is not None:
            for key in list(self.response_waiters.keys()):
                self.response_waiters[key].set(ResponsePayload(
                    type="response", source=self.id_, target=self.id_,
                    session="", status="Warning", data=(
                        "ConnectionClosedOnRequest", (code, reason,),
                        "The request was not completed because the client disconnected from WebSocket."
                    )
                ))
            self.response_waiters = {}