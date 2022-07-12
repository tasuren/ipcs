# ipcs - Server

from typing import Any

from logging import getLogger

from asyncio import Future

from websockets.exceptions import ConnectionClosed
from websockets.server import serve

from orjson import loads, dumps

from .types_ import WebSocketProtocol, RequestPayload, ResponsePayload
from .connection import Connection
from .client import AbcClient


__all__ = ("ConnectionForServer", "Server")
logger = getLogger("ipcs.server")


class ConnectionForServer(Connection):
    ws: WebSocketProtocol

    async def close(self) -> None:
        await super().close()
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
        await ws.send(dumps(list(self.connections.keys())))
        # メインプロセスを実行する。
        await self.request_all("on_connect", id_)
        self.dispatch("on_connect", self.connections[id_])
        try:
            while True:
                data: RequestPayload | ResponsePayload = loads(await ws.recv())
                if data["target"] == self.id_:
                    self._on_receive(data)
                else:
                    self._pass_data(data)
        except ConnectionClosed:
            await self.request_all("on_disconnect", id_)
            self.dispatch("on_disconnect", self.connections[id_])

    async def _send(self, data: RequestPayload | ResponsePayload) -> None:
        if data["target"] == self.id_:
            self._on_receive(data)
        else:
            self._pass_data(data)

    def _pass_data(self, data: RequestPayload | ResponsePayload) -> None:
        # 渡されたデータをそのデータで指定されている宛先に送信します。
        for connection in self.connections.values():
            if connection.id_ == data["target"]:
                self.loop.create_task(
                    connection.ws.send(dumps(data)),
                    name="ipcs: Pass data: %s" % data["session"]
                )
        else:
            ... # TODO: 宛先が不明なリクエストまたはレスポンスがあった場合は警告を表示する。

    async def start(self, *args: Any, **kwargs: Any) -> None:
        await super().start()
        for_loop = Future[None]()
        async with serve(self.on_connect, *args, **kwargs): # type: ignore
            await for_loop

    async def close(self, code: int = 1000, reason: str = "...") -> None:
        self._code, self._reason = code, reason
        await super().close(code, reason)