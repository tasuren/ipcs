# ipcs - Client

from __future__ import annotations

from typing import TypeAlias, Generic, Concatenate, TypeVar, ParamSpec, Any, cast
from collections.abc import Callable, Coroutine

from inspect import ismethod
from traceback import print_exc

from dataclasses import dataclass
from collections import defaultdict

from uuid import uuid4
from time import time
import asyncio

from abc import ABC, abstractmethod

from websockets.exceptions import ConnectionClosed
from websockets.legacy.client import connect

from orjson import dumps, loads

from .types_ import RequestPayload, ResponsePayload, WebSocketProtocol, Id, Session, Route
from .errors import RouteIsNotFound
from .utils import SimpleAttrDict, error_to_str, payload_to_str
from .connection import Connection


__all__ = ("Request", "AbcClient", "Client")


@dataclass
class Request:
    source: Connection
    session: Session
    route: Route
    raw: RequestPayload

    def __str__(self) -> str:
        return "<Request source={} session={} route={}>".format(
            self.source, self.session, self.route
        )

    @classmethod
    def from_payload(cls, source: Connection, data: RequestPayload) -> Request:
        return cls(source, data["session"], data["route"], data)


def _get_func_name(func: Callable) -> str:
    # 関数またはメソッドの名前を取得します。
    return func.__func__.__name__ if ismethod(func) else getattr(func, "__name__") # type: ignore


RhP = ParamSpec("RhP")
RhReT = TypeVar("RhReT")
RouteHandler: TypeAlias = Callable[..., Coroutine[Any, Any, Any]]
ListenerHandler: TypeAlias = Callable[..., Any | Coroutine[Any, Any, Any]]
LiT = TypeVar("LiT", bound=ListenerHandler)
ConnectionT = TypeVar("ConnectionT", bound=Connection)
class AbcClient(ABC, Generic[ConnectionT]):

    _loop: asyncio.AbstractEventLoop | None = None
    ws: WebSocketProtocol | None = None

    def __init__(self, id_: Id, timeout: float = 8.0):
        self.routes: dict[str, RouteHandler] = {}
        self._secret_routes: dict[str, RouteHandler] = {}
        self.listeners: defaultdict[str, list[ListenerHandler]] = defaultdict(list)
        self.connections: SimpleAttrDict[ConnectionT] = SimpleAttrDict()
        self.id_, self.timeout = id_, timeout

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        return self._loop

    def add_listener(self, func: ListenerHandler, name: str | None = None) -> None:
        self.listeners[name or _get_func_name(func)].append(func)

    def remove_listener(self, target: ListenerHandler | str) -> None:
        for name, listeners in list(self.listeners.items()):
            if target in listeners:
                listeners.remove(target) # type: ignore
            elif target == name:
                del self.listeners[name]

    def listen(self, name: str | None = None) -> Callable[[LiT], LiT]:
        def decorator(func: LiT) -> LiT:
            self.add_listener(func, name)
            return func
        return decorator

    def dispatch(self, name: str, *args: Any, **kwargs: Any) -> None:
        for listener in self.listeners[name]:
            if asyncio.iscoroutinefunction(listener):
                self.loop.create_task(
                    listener(*args, **kwargs),
                    name="ipcs: Dispatch event: %s" % name
                )
            else:
                listener(*args, **kwargs)

    def add_route(
        self, func: Callable[Concatenate[Request, RhP], Coroutine[Any, Any, RhReT]],
        name: str | None = None,
        secret: bool = False
    ) -> None:
        (self._secret_routes if secret else self.routes)[name or _get_func_name(func)] = func

    def route(self, name: str | None = None, secret: bool = False) -> Callable[
        [Callable[Concatenate[Request, RhP], Coroutine[Any, Any, RhReT]]],
        Callable[Concatenate[Request, RhP], Coroutine[Any, Any, RhReT]]
    ]:
        def decorator(func):
            self.add_route(func, name, secret)
            return func
        return decorator

    def generate_session(self) -> Session:
        return f"{self.id_}-{uuid4()}-{time()}"

    def _on_receive(self, payload: RequestPayload | ResponsePayload) -> None:
        # データを取得した際に呼ばれるべき関数です。
        self.dispatch("on_receive", payload)
        print(1, payload)
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
            print(self._secret_routes)
            if payload["route"] not in self.routes and (
                payload["secret"] and payload["route"] not in self._secret_routes
            ):
                raise RouteIsNotFound("The route is not found: %s" % payload_to_str(payload))
            result = (
                self._secret_routes[payload["route"]]
                if payload["secret"] else
                self.routes[payload["route"]]
            )(
                Request.from_payload(self.connections[self.id_], payload),
                *payload["args"], **payload["kwargs"]
            )
        except Exception as error:
            print_exc() # TODO: logger.exceptionにする。
            data["result"] = error_to_str(error)
        else:
            data["result"] = result
            data["status"] = "ok"
        self.dispatch("on_response", data)
        await self._send(data)

    async def _send(self, data: RequestPayload | ResponsePayload) -> None:
        assert self.ws is not None
        await self.ws.send(dumps(data))

    async def request_all(
        self, route: Route, *args: Any,
        key: Callable[[Connection], bool] = lambda _: True,
        asyncio_gather_kwargs: dict[str, Any] | None = None,
        **kwargs: Any
    ) -> tuple[Any]:
        return await asyncio.gather(*map(
            lambda c: c.request(route, *args, **kwargs),
            filter(key, self.connections.values())
        ), **(asyncio_gather_kwargs or {}))

    @abstractmethod
    async def start(self, *args: Any, **kwargs: Any) -> None:
        self.dispatch("on_start")

    def _close_connection(self, id_or_connection: Id | Connection) -> None:
        # 接続を消します。
        if isinstance(id_or_connection, Id):
            id_or_connection = self.connections[id_or_connection]
        self.loop.create_task(id_or_connection.close(), name="ipcs: Close connection")
        del self.connections[id_or_connection.id_]

    @abstractmethod
    async def close(self, code: int = 1000, reason: str = "...") -> None:
        self.dispatch("on_close", code, reason)
        for connection in list(self.connections.values()):
            self._close_connection(connection)

    def run(self, *args: Any, **kwargs: Any) -> None:
        asyncio.run(self.start(*args, **kwargs))


class Client(AbcClient[Connection]):

    ready: asyncio.Event

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        # 隠しRouteを追加する。
        self.add_route(self._on_connect, "on_connect", True)
        self.add_route(self._on_disconnect, "on_disconnect", True)

    async def _on_connect(self, _, id_: Id) -> None:
        self.connections[id_] = Connection(self, id_)
        self.dispatch("on_connect", self.connections[id_])

    async def _on_disconnect(self, _, id_: Id) -> None:
        self._close_connection(id_)
        self.dispatch("on_disconnect", self.connections[id_])

    async def start(self, *args: Any, **kwargs: Any) -> None:
        self.ready = asyncio.Event()
        self.is_closed = False
        async for ws in connect(*args, **kwargs):
            self.ready.clear()
            self.ws = cast(WebSocketProtocol, ws)
            # 認証を行う。
            await self.ws.send(f"verify:{self.id_}")
            print(1)
            if (data := await self.ws.recv()) == "error":
                print(data)
                raise ValueError("The ID had already used by another client.")
            # 現在接続されているクライアントを`.connections`に入れる。
            for id_ in loads(data):
                self.connections[id_] = Connection(self, id_)
            # データの取得を開始する。
            await super().start()
            try:
                while True:
                    self._on_receive(loads(await self.ws.recv()))
            except ConnectionClosed:
                if self.is_closed:
                    break

    async def close(self, code: int = 1000, reason: str = "...") -> None:
        await super().close(code, reason)
        self.is_closed = True
        await self.close(code, reason)