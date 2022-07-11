# ipcs - Client

from __future__ import annotations

from typing import Protocol, TypeVar, Any
from collections.abc import Callable

from inspect import ismethod
from traceback import print_exc

from dataclasses import dataclass

from uuid import uuid4
from time import time
import asyncio

from abc import ABC, abstractmethod

from websockets.exceptions import ConnectionClosedOK
from websockets.client import WebSocketClientProtocol
from websockets.legacy.client import connect

from orjson import dumps, loads

from .types import RequestPayload, ResponsePayload, Id, Session, Route
from .errors import RouteIsNotFound
from .utils import SimpleAttrDict, error_to_str, payload_to_str
from .connection import Connection


__all__ = ("Request", "RouteHandler", "AbcClient", "Client")


@dataclass
class Request:
    source: Connection
    session: Session
    route: Route
    raw: RequestPayload

    @classmethod
    def from_payload(cls, data: RequestPayload) -> Request:
        return cls(data["source"], data["session"], data["route"], data)


class RouteHandler(Protocol):
    def __call__(self, request: Request, *args: Any, **kwargs: Any) -> Any:
        ...


EhT = TypeVar("EhT", bound=RouteHandler)
class AbcClient(ABC):
    def __init__(self, id_: Id, timeout: float = 8.0):
        self.routes: dict[str, RouteHandler] = {}
        # self.listeners: defaultdict[str, list] = defaultdict(list)
        self.connections: SimpleAttrDict[Connection] = SimpleAttrDict()
        self.id_, self.timeout = id_, timeout
        self._loop = None

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        return self._loop

    async def send(self, target: Id, route: Route, *args: Any, **kwargs: Any) -> Any:
        if target in self.connections:
            return await self.connections[target].send(route, *args, **kwargs)
        else:
            raise ValueError("That connection is not found.")

    async def send_all(
        self, route: Route, *args: Any,
        key: Callable[[Connection], bool] = lambda _: True,
        asyncio_gather_kwargs: dict[str, Any] | None = None,
        **kwargs: Any
    ) -> list[Any]:
        return await asyncio.gather(*map(
            lambda c: c.send(route, *args, **kwargs),
            filter(key, self.connections.values())
        ), **asyncio_gather_kwargs)

    def add_route(self, func: RouteHandler, name: str | None = None) -> None:
        self.routes[
            (func.__func__.__name__ if ismethod(func) else func.__name__)
            if name is None else name
        ] = func

    def route(self, name: str | None = None) -> Callable[[EhT], EhT]:
        def decorator(func: EhT) -> EhT:
            self.add_route(func, name)
            return func
        return decorator

    def generate_session(self) -> Session:
        return f"{self.id_}-{uuid4()}-{time()}"

    def _on_receive(self, payload: RequestPayload | ResponsePayload) -> None:
        # データを取得した際に呼ばれるべき関数です。
        if payload["types"] == "request":
            # リクエストがされたのなら、そのリクエストに応じる。
            self.loop.create_task(
                self._run_route(payload),
                name="ipcs: Run route: %s" % payload["session"]
            )
        else:
            # レスポンスが来たのなら、そのレスポンスを待機しているEventを探し待機終了させる。
            if payload["source"] in self.connections:
                try:
                    self.connections[payload["source"]].queues[payload["session"]] \
                        .set(payload["result"])
                except KeyError:
                    ... # TODO: どこで送ったのかわからない謎のレスポンスが来たのなら、loggerで警告を出すようにする。
            else:
                ... # TODO: 見ず知らずのクライアントからレスポンスが来たのなら、loggerで警告を表示するようにする。

    async def _run_route(self, payload: RequestPayload) -> None:
        # 渡されたリクエストデータからRouteを動かして、結果をそのリクエストを送ったクライアントに送り返します。
        data = ResponsePayload(
            source=self.id_, target=payload["source"], secret=payload["secret"],
            session=payload["session"], route=payload["route"], types="response",
            status="error", result=None
        )
        try:
            if payload["route"] not in self.routes:
                raise RouteIsNotFound("The route is not found: %s" % payload_to_str(payload))
            result = self.routes[payload["route"]](
                Request.from_payload(payload),
                *payload["args"], **payload["kwargs"]
            )
        except Exception as error:
            print_exc() # TODO: logger.exceptionにする。
            data["result"] = error_to_str(error)
        else:
            data["result"] = result
            data["status"] = "ok"
        await self.send(data)

    @abstractmethod
    async def send(self, payload: RequestPayload | ResponsePayload) -> None:
        ...

    @abstractmethod
    async def start(self, *args: Any, **kwargs: Any) -> None:
        ...


class Client(AbcClient):

    ws: WebSocketClientProtocol | None = None
    ready: asyncio.Event
    receiver: asyncio.Task

    async def start(self, uri: str, **kwargs: Any) -> None:
        self.ready = asyncio.Event()
        async for ws in connect(uri, **kwargs):
            self.ready.clear()
            self.ws = ws
            # 認証を行う。
            await self.ws.send("verify")
            if (data := await self.ws.recv()) == "error":
                raise ValueError("The ID had already used by another client.")
            # 現在接続されているクライアントを`.connections`に入れる。
            for id_ in loads(data):
                self.connections[id_] = Connection(self)
            # データの取得を開始する。
            try:
                while True:
                    self._on_receive(await self.ws.recv())
            except ConnectionClosedOK:
                break

    async def send(self, payload: RequestPayload | ResponsePayload) -> None:
        await self.ws.send(dumps(payload))