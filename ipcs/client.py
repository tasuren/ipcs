# ipcs - Client

from __future__ import annotations
from tkinter.messagebox import IGNORE

from typing import TypeAlias, Generic, Concatenate, TypeVar, ParamSpec, Any, cast
from collections.abc import Callable, Coroutine

from inspect import ismethod
from traceback import print_exc
from logging import getLogger

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


__all__ = ("Request", "AbcClient", "Client", "logger")
logger = getLogger("ipcs")


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


def _process_function(func: Callable, name: str | None = None) -> str:
    # 関数またはメソッドの名前を取得します。
    func = func.__func__ if ismethod(func) else func # type: ignore
    setattr(func, "__ipcs_is_coroutine_function__", asyncio.iscoroutinefunction(func))
    return name or getattr(func, "__name__")


RhP = ParamSpec("RhP")
RhReT = TypeVar("RhReT")
RouteHandler: TypeAlias = Callable[..., Coroutine[Any, Any, Any]]
EventHandler: TypeAlias = Callable[..., Any | Coroutine[Any, Any, Any]]
LiT = TypeVar("LiT", bound=EventHandler)
ConnectionT = TypeVar("ConnectionT", bound=Connection)
class AbcClient(ABC, Generic[ConnectionT]):

    _loop: asyncio.AbstractEventLoop | None = None
    ws: WebSocketProtocol | None = None

    def __init__(self, id_: Id, timeout: float = 8.0):
        self.routes: dict[str, RouteHandler] = {}
        self._secret_routes: dict[str, RouteHandler] = {}
        self.listeners: defaultdict[str, list[EventHandler]] = defaultdict(list)
        self.connections: SimpleAttrDict[ConnectionT] = SimpleAttrDict()
        self.id_, self.timeout = id_, timeout

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        return self._loop

    def add_listener(self, func: EventHandler, name: str | None = None) -> None:
        self.listeners[_process_function(func, name)].append(func)

    def remove_listener(self, target: EventHandler | str) -> None:
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

    _IGNORE_EXC = "Ignoring exception %s:"

    async def _dispatch(self, event_name: str, listener: EventHandler, args: Any, kwargs: Any):
        try:
            return await listener(*args, **kwargs) \
                if getattr(listener, "__ipcs_is_coroutine_function__") else \
                listener(*args, **kwargs)
        except Exception:
            logger.exception(self._IGNORE_EXC % f"in {event_name}:")

    def dispatch(self, name: str, *args: Any, **kwargs: Any) -> None:
        for listener in self.listeners[name]:
            self.loop.create_task(
                self._dispatch(name, listener, args, kwargs),
                name="ipcs: Dispatch event: %s" % name
            )

    def add_route(
        self, func: Callable[Concatenate[Request, RhP], Coroutine[Any, Any, RhReT]],
        name: str | None = None,
        secret: bool = False
    ) -> None:
        (self._secret_routes if secret else self.routes)[_process_function(func, name)] = func

    def route(self, name: str | None = None, secret: bool = False) -> Callable[
        [Callable[Concatenate[Request, RhP], Coroutine[Any, Any, RhReT] | RhReT]],
        Callable[Concatenate[Request, RhP], Coroutine[Any, Any, RhReT] | RhReT]
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
        logger.info("Received data: %s" % payload_to_str(payload))
        if payload["type"] == "request":
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
                        .set(payload)
                except KeyError:
                    logger.warning("Got a response for which the requestor does not exist: %s" % payload_to_str(payload))
            else:
                logger.warning("Got a response that I don't know from which client the response came: %s" % payload_to_str(payload))

    async def _run_route(self, payload: RequestPayload) -> None:
        # 渡されたリクエストデータからRouteを動かして、結果をそのリクエストを送ったクライアントに送り返します。
        logger.debug("Running route: %s(is_secret=%s)(*%s, **%s)" % (
            payload["route"], payload["secret"], payload["args"], payload["kwargs"]
        ))
        data = ResponsePayload(
            source=self.id_, target=payload["source"], secret=payload["secret"],
            session=payload["session"], route=payload["route"], type="response",
            status="error", result=None
        )
        try:
            if payload["route"] not in self.routes and (
                payload["secret"] and payload["route"] not in self._secret_routes
            ):
                raise RouteIsNotFound("The route is not found: %s" % payload_to_str(payload))
            function = self._secret_routes[payload["route"]] \
                if payload["secret"] else \
                self.routes[payload["route"]]
            result = function(
                Request.from_payload(self.connections[self.id_], payload),
                *payload["args"], **payload["kwargs"]
            )
            if getattr(function, "__ipcs_is_coroutine_function__"):
                result = await result
        except Exception as error:
            logger.exception(self._IGNORE_EXC % f"in route '{payload['route']}'")
            data["result"] = error_to_str(error)
        else:
            data["result"] = result
            data["status"] = "ok"
        logger.info("Response: %s" % payload_to_str(payload))
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
        self._closing = False
        self.dispatch("on_ready")

    async def _close_connection(self, id_or_connection: Id | Connection) -> None:
        # 接続を消します。
        logger.info("Closing connection: %s" % id_or_connection)
        if isinstance(id_or_connection, Id):
            id_or_connection = self.connections[id_or_connection]
        await id_or_connection.close()
        del self.connections[id_or_connection.id_]

    @abstractmethod
    async def close(self, code: int = 1000, reason: str = "...") -> None:
        logger.info("Closing...")
        self._closing = True
        self.dispatch("on_close", code, reason)
        await asyncio.gather(*(
            self._close_connection(connection)
            for connection in list(self.connections.values())
        ))

    async def _wrapped_start(self, args, kwargs) -> None:
        try:
            await self.start(*args, **kwargs)
        finally:
            await self.close()

    def run(self, *args: Any, **kwargs: Any) -> None:
        try:
            asyncio.run(self._wrapped_start(args, kwargs))
        except KeyboardInterrupt:
            ...


class Client(AbcClient[Connection]):

    ready: asyncio.Event

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        # 隠しRouteを追加する。
        self.add_route(self._on_connect, "on_connect", True)
        self.add_route(self._on_disconnect, "on_disconnect", True)

    async def _on_connect(self, _, id_: Id) -> None:
        self.connections[id_] = Connection(self, id_)
        logger.info("Connected new client to server: %s" % id_)
        self.dispatch("on_connect", id_)

    async def _on_disconnect(self, _, id_: Id) -> None:
        await self._close_connection(id_)
        logger.info("Disconnected client from server: %s" % id_)
        self.dispatch("on_disconnect", id_)

    _CONNECTING = "Connecting to server..."

    async def start(self, *args: Any, **kwargs: Any) -> None:
        self.ready = asyncio.Event()
        self.is_closed = False
        logger.info(self._CONNECTING)
        async for ws in connect(*args, **kwargs):
            self.ready.clear()
            self.ws = cast(WebSocketProtocol, ws)
            # 認証を行う。
            logger.info("Verifing...")
            await self.ws.send(f"verify:{self.id_}")
            if (data := await self.ws.recv()) == "error":
                raise ValueError("The ID had already used by another client.")
            logger.info("Loading connections...")
            # 現在接続されているクライアントを`.connections`に入れる。
            for id_ in loads(data):
                self.connections[id_] = Connection(self, id_)
            # データの取得を開始する。
            logger.info("Connected")
            self.ready.set()
            await super().start()
            try:
                while True:
                    self._on_receive(loads(await self.ws.recv()))
            except ConnectionClosed:
                if self.is_closed:
                    break
            self.dispatch("on_disconnect_from_server")
            logger.info(self._CONNECTING)

    async def close(self, code: int = 1000, reason: str = "...") -> None:
        await super().close(code, reason)
        self.is_closed = True
        if self.ws is not None:
            await self.ws.close(code, reason)