# ipcs - Client

from __future__ import annotations

from typing import TypeAlias, Generic, TypeVar, ParamSpec, Any, cast
from collections.abc import Callable, Coroutine

from inspect import ismethod, getfile
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

from .types_ import RequestPayload, ResponsePayload, WebSocketProtocol
from .errors import IdIsNotFound, RequestError
from .utils import SimpleAttrDict, error_to_str, payload_to_str
from .connection import Connection


__all__ = ("Request", "AbcClient", "Client", "logger")
logger = getLogger("ipcs")
"Log output destination. ipcs use logging from the standard library."


def _debug():
    import logging
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(name)s] [%(levelname)s] %(message)s"))
    logging.basicConfig(level=logging.DEBUG, handlers=(handler,))
# _debug()


@dataclass
class Request:
    "Data class for storing request information."

    source: Connection
    "The sender who made the request."
    session: str
    "str ID to identify the request."
    route: str
    "The name of what str of execution should be executed in the request."
    raw: RequestPayload
    "This is the raw data of the request."

    def __str__(self) -> str:
        return "<Request source={} session={} route={}>".format(
            self.source, self.session, self.route
        )

    @classmethod
    def from_payload(cls, source: Connection, data: RequestPayload) -> Request:
        "Create an instance of this class from the requestor connection and raw data."
        return cls(source, data["session"], data["route"], data)


def _process_function(func: Callable, name: str | None = None) -> str:
    # 関数またはメソッドの名前を取得します。
    func = func.__func__ if ismethod(func) else func # type: ignore
    setattr(func, "__ipcs_is_coroutine_function__", asyncio.iscoroutinefunction(func))
    return name or getattr(func, "__name__")


RhP = ParamSpec("RhP")
RhReT = TypeVar("RhReT")
strHandler: TypeAlias = Callable[..., Any | Coroutine[Any, Any, Any]]
EventHandler: TypeAlias = Callable[..., Any | Coroutine[Any, Any, Any]]
LiT = TypeVar("LiT", bound=EventHandler)
ConnectionT = TypeVar("ConnectionT", bound=Connection)
class AbcClient(ABC, Generic[ConnectionT]):
    """Base class for the client class.

    Args:
        id_: Client ID. It must be unique among clients connecting to the server.
        timeout: When a client makes a request, how long it waits for that request.

    Attributes:
        routes: A dictionary for storing registered strs.
        listeners: A dictionary to store listeners for registered events.
        connections: A dictionary to store :class:`ipcs.connection.Connection` of clients connecting to the server.
            This dictionary uses :class:`ipcs.utils.SimpleAttrDict` and allows access to dictionary values from attributes.
        id_: Client ID.
        timeout: When a client makes a request, how long it waits for that request."""

    _loop: asyncio.AbstractEventLoop | None = None
    _closing = False
    ws: WebSocketProtocol | None = None
    "The web socket used by the client to communicate with the server."

    def __init__(self, id_: str, timeout: float = 8.0) -> None:
        self.routes: dict[str, strHandler] = {}
        self._secret_routes: dict[str, strHandler] = {}
        self.listeners: defaultdict[str, list[EventHandler]] = defaultdict(list)
        self.connections: SimpleAttrDict[ConnectionT] = SimpleAttrDict()
        self.id_, self.timeout = id_, timeout

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        "The event loop used by the client."
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        return self._loop

    def add_listener(self, func: EventHandler, name: str | None = None) -> None:
        """Add a function (called a listener) that executes the event when it occurs.
        The default available events can be found in the ``EventReference`` menu.

        Args:
            func: Function to be executed when an event occurs.
            name: The name of what event to listen for. If ``None``, the function name is used instead."""
        self.listeners[_process_function(func, name)].append(func)

    def remove_listener(self, target: EventHandler | str) -> None:
        """The name of what event to listen for. If ``None``, the function name is used instead.

        Args:
            target: The name or function of the listener to be deleted."""
        for name, listeners in list(self.listeners.items()):
            if target in listeners:
                listeners.remove(target) # type: ignore
            elif target == name:
                del self.listeners[name]

    def listen(self, name: str | None = None) -> Callable[[LiT], LiT]:
        """Decorator version of :meth:`.add_listener`.

        Args:
            name: The name of what event to listen for. If ``None``, the function name is used instead."""
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
        """Raises an event.

        Args:
            name: The name of the event.
            *args: The arguments to be passed to the event handler (listener).
            **kwargs: The keyword arguments to be passed to the event handler (listener)."""
        for listener in self.listeners[name]:
            self.loop.create_task(
                self._dispatch(name, listener, args, kwargs),
                name="ipcs: Dispatch event: %s" % name
            )

    def set_route(self, func: strHandler, name: str | None = None, secret: bool = False) -> None:
        """Registers a function to respond to a request from another client.
        Now the registered function can be called by another client with the name used for registration. (This is called a request.)
        Such a function is also called a str.

        Args:
            func: Function to register as str.
            name: str Name. If ``None``, the function name is used.
            secret: If it is ``True``, function is to be registered as a hidden str.
                This is used internally in ipcs to add a str to receive information when a client connects from the server to a new connection, for example.
                A str registered in this way cannot be deleted.
                Therefore, it should not be used outside of ipcs."""
        (self._secret_routes if secret else self.routes)[_process_function(func, name)] = func

    def remove_route(self, target: strHandler | str) -> None:
        """Delete a str.

        Args:
            target: Name or function of str to be deleted."""
        for key, route in list(self.routes.items()):
            if key == target or route == target:
                del self.routes[key]

    def route(self, name: str | None = None, secret: bool = False) -> Callable[[RhReT], RhReT]:
        """Decorator version of :meth:`.set_route`.

        Args:
            name: Please read the description in :meth:`.set_route`.
            secret: Please read the description in :meth:`.set_route`."""
        def decorator(func):
            self.set_route(func, name, secret)
            return func
        return decorator

    def generate_session(self) -> str:
        "Generates a session ID used to identify the request.\nThis is used inside ipcs."
        return f"{self.id_}-{uuid4()}-{time()}"

    def _on_receive(self, payload: RequestPayload | ResponsePayload) -> None:
        # データを取得した際に呼ばれるべき関数です。
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
                    self.connections[payload["source"]].queue[payload["session"]] \
                        .set(payload)
                except KeyError:
                    logger.warning("Got a response for which the requestor does not exist: %s" % payload_to_str(payload))
            else:
                logger.warning("Got a response that I don't know from which client the response came: %s" % payload_to_str(payload))

    async def _run_route(self, payload: RequestPayload) -> None:
        # 渡されたリクエストデータからstrを動かして、結果をそのリクエストを送ったクライアントに送り返します。
        logger.debug("Running route: routes[route_mode(is_secret=%s)]%s(*%s, **%s)" % (
            payload["route"], payload["secret"], payload["args"], payload["kwargs"]
        ))
        data = ResponsePayload(
            source=self.id_, target=payload["source"], secret=payload["secret"],
            session=payload["session"], route=payload["route"], type="response",
            status="error", result=None
        )
        function = None
        try:
            if payload["route"] not in self.routes and (
                payload["secret"] and payload["route"] not in self._secret_routes
            ):
                raise IdIsNotFound("The route is not found: %s" % payload_to_str(payload))
            function = self._secret_routes[payload["route"]] \
                if payload["secret"] else \
                self.routes[payload["route"]]
            result = function(
                Request.from_payload(self.connections[payload["source"]], payload),
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
        try:
            await self._send(data)
        except TypeError:
            logger.error(
                "The return value was something that could not be made into data: %s"
                    % None if function is None else getfile(function)
            )

    async def _send(self, data: RequestPayload | ResponsePayload) -> None:
        assert self.ws is not None
        await self.ws.send(dumps(data))

    async def request(self, id_: str, route: str, *args: Any, **kwargs: Any) -> Any:
        """Sends a request to the specified connection.  
        Alias of :meth:`ipcs.connection.Connection.request`.

        Args:
            id_: The id of the connection.
            route: The route to request.
            *args: The arguments to be passed to str.
            **kwargs:  The keyword arguments to be passed to str.

        Raises:
            ipcs.errors.FailedToProcessError: Occurs when an error occurs at the connection site.
            ipcs.errors.FailedToRequestError: Occurs when an error occurs while sending a request.
            ipcs.errors.ClosedConnectionError: Occurs when the connection is broken and a request cannot be made."""
        return await self.connections[id_].request(route, *args, **kwargs)

    async def request_all(
        self, route: str, *args: Any,
        key_: Callable[[Connection], bool] = lambda _: True,
        **kwargs: Any
    ) -> dict[str, tuple[None | Any, None | RequestError]]:
        """Make requests to everyone except yourself.

        Args:
            route: The name of the str to request.
            *args: The arguments to be passed to str.
            key_: Function executed to determine if a request should be sent.
                This can be used, for example, to send a request only to IDs that conform to certain rules.
            **kwargs: The keyword arguments to be passed to str.

        Returns:
            The return value is a dictionary whose key is the ID of the requestor and whose value is a tuple containing the return value and the error.
            If no error occurred, the error value is ``None``."""
        data = {}
        for id_, task in [(c.id_, self.loop.create_task(
            c.request(route, *args, **kwargs),
            name="ipcs: request_all: %s" % c.id_
        )) for c in filter(
            lambda c: key_(c) and c.id_ != self.id_,
            self.connections.values()
        )]:
            result, error = None, None
            try:
                result = await task
            except RequestError as e:
                error = e
            data[id_] = (result, error)
        return data

    @abstractmethod
    async def start(self, *args: Any, **kwargs: Any) -> None:
        "This method is not fully implemented. Implemented are :class:`ipcs.client.Client` and :class:`ipcs.server.Server`."
        self._closing = False
        self.dispatch("on_ready")

    async def _close_connection(self, id_or_connection: str | Connection) -> None:
        # 接続を消します。
        logger.info("Closing connection: %s" % id_or_connection)
        if isinstance(id_or_connection, str):
            id_or_connection = self.connections[id_or_connection]
        await id_or_connection.close()

    @abstractmethod
    async def close(self, code: int = 1000, reason: str = "...") -> None:
        "This method is not fully implemented. Implemented are :class:`ipcs.client.Client` and :class:`ipcs.server.Server`."
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
        except Exception:
            logger.exception("An error occurred during the WebSocket communication process:")
        finally:
            await self.close()

    def run(self, *args: Any, **kwargs: Any) -> None:
        """Start client.
        It internally uses ``run`` in the standard library asyncio to run :meth:`ipcs.AbcClient.start`.

        Args:
            *args: The arguments to be passed to :meth:`ipcs.AbcClient.start`.
            **kwrags: The keyword arguments to be passed to :meth:`ipcs.AbcClient.start`."""
        try:
            asyncio.run(self._wrapped_start(args, kwargs))
        except KeyboardInterrupt:
            ...


class Client(AbcClient[Connection]):
    "This is the class of the client for ipc communication with the server."

    ready: asyncio.Event
    """This is an ``Event`` in the standard library asyncio to put if it has already started (connected to the server).
    You can use ``await ready.wait()`` to wait until it starts."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # 隠しstrを追加する。
        self.set_route(self._on_connect, "on_connect", True)
        self.set_route(self._on_disconnect, "on_disconnect", True)

    def _on_connect(self, _, id_: str) -> None:
        self.connections[id_] = Connection(self, id_)
        logger.info("Connected new client to server: %s" % id_)
        self.dispatch("on_connect", id_)

    async def _on_disconnect(self, _, id_: str) -> None:
        await self._close_connection(id_)
        logger.info("Disconnected client from server: %s" % id_)
        self.dispatch("on_disconnect", id_)

    _CONNECTING = "Connecting to server..."

    async def start(self, *args: Any, reconnect: bool = True, **kwargs: Any) -> None:
        """Starts (connects) client.

        Args:
            *args: The arguments to be passed to ``connect`` in the third party library websockets.
                Details of ``connect`` is `here <https://websockets.readthedocs.io/en/stable/reference/client.html#websockets.client.connect>`_.
            reconnect: Whether or not to make the reconnection.
            **kwargs: The keyword arguments to be passed to ``connect`` in the third party library websockets.
                Details of ``connect`` is `here <https://websockets.readthedocs.io/en/stable/reference/client.html#websockets.client.connect>`_."""
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
            # メインプロセスを実行する。
            try:
                while True:
                    self._on_receive(loads(await self.ws.recv()))
            except ConnectionClosed:
                ...
            logger.info("Disconnected from server")
            self.dispatch("on_disconnect_from_server")
            if not reconnect or self.is_closed:
                break
            logger.info(self._CONNECTING)

    async def close(self, code: int = 1000, reason: str = "...") -> None:
        """Disconnects the client from the server.

        Args:
            code: This code is used when cutting with a websocket.
            reason: This reason is used when cutting with a websocket."""
        await super().close(code, reason)
        self.is_closed = True
        if self.ws is not None:
            await self.ws.close(code, reason)