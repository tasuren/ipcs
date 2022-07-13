# ipcs - Server

from typing import Any

from logging import getLogger

from asyncio import Future

from websockets.exceptions import ConnectionClosed
from websockets.server import serve

from orjson import loads, dumps

from .types_ import WebSocketProtocol, RequestPayload, ResponsePayload
from .utils import payload_to_str
from .connection import Connection
from .client import AbcClient, logger


__all__ = ("ConnectionForServer", "Server")


class ConnectionForServer(Connection):

    ws: WebSocketProtocol

    async def close(self) -> None:
        await super().close()
        if not self.client._closing and not self.ws.closed:
            await self.ws.close(self.client._code, self.client._reason) # type: ignore


class Server(AbcClient[ConnectionForServer]):
    async def on_connect(self, ws: WebSocketProtocol) -> None:
        # 認証を行う。
        id_ = (await ws.recv())[7:]
        assert isinstance(id_, str)
        if id_ in self.connections:
            return await ws.send("error")
        self.connections[id_] = ConnectionForServer(self, id_)
        self.connections[id_].ws = ws
        print(1, self.id_)
        await ws.send(dumps(list(self.connections.keys()) + [self.id_]))
        # メインプロセスを実行する。
        self.loop.create_task(
            self.request_all("on_connect", id_, ipcs_secret=True),
            name="ipcs: Request on_connect secret request: %s" % id_
        )
        self.dispatch("on_connect", id_)
        try:
            while True:
                data: RequestPayload | ResponsePayload = loads(await ws.recv())
                if data["target"] == self.id_:
                    self._on_receive(data)
                else:
                    self._transfer_data(data)
        except ConnectionClosed:
            if not self._closing:
                await self._close_connection(id_)
                self.loop.create_task(
                    self.request_all("on_disconnect", id_, ipcs_secret=True),
                    name="ipcs: Request on_disconnect secret request: %s" % id_
                )
                self.dispatch("on_disconnect", id_)

    async def _send(self, data: RequestPayload | ResponsePayload) -> None:
        if data["target"] == self.id_:
            self._on_receive(data)
        else:
            self._transfer_data(data)

    def _transfer_data(self, data: RequestPayload | ResponsePayload) -> None:
        # 渡されたデータをそのデータで指定されている宛先に送信します。
        for connection in self.connections.values():
            if connection.id_ == data["target"]:
                logger.info("Transfer data: %s" % payload_to_str(data))
                self.loop.create_task(
                    connection.ws.send(dumps(data)),
                    name="ipcs: Pass data: %s" % data["session"]
                )
                break
        else:
            logger.warning("I tried to transfer data but could not find a destination: %s" % payload_to_str(data))

    async def start(self, *args: Any, **kwargs: Any) -> None:
        await super().start()
        for_loop = Future[None]()
        async with serve(self.on_connect, *args, **kwargs): # type: ignore
            await for_loop

    async def close(self, code: int = 1000, reason: str = "...") -> None:
        self._code, self._reason = code, reason
        await super().close(code, reason)