# ipcs - Client

from __future__ import annotations

from typing import TypeVar, Optional, Any
from collections.abc import Callable

from traceback import format_exc
from logging import getLogger

from inspect import iscoroutine
from uuid import uuid4
import asyncio

from websockets.exceptions import ConnectionClosed, ConnectionClosedOK
from websockets.client import WebSocketClientProtocol, connect

from orjson import dumps, loads

from .types_ import Route, Identifier, Payload, RequestPayload, ResponsePayload
from .utils import DataEvent, EventManager, _get_exception_name, _data_str
from . import exceptions


__all__ = ("IpcsClient", "logger")
logger = getLogger("ipcs.client")
"Logger of ``logging`` in the standard library.\nName: ``ipcs.client``"


RfT = TypeVar("RfT", bound=Route)
class IpcsClient(EventManager):
    """IPC client to connect to :class:`IpcServer`.

    Args:
        id_: ID for client identification
        timeout: Seconds until request times out"""

    ws: Optional[WebSocketClientProtocol] = None
    "This should assigned an instance of the class used for websocket communication."
    me: Identifier
    "An identification ID that indicates who you are in ipc communication."
    timeout: float
    "The number of seconds to time out."
    routes: dict[str, Route]
    "The Route is stored here."
    response_waiters: dict[str, DataEvent[ResponsePayload]]
    "This is where the :class:`DataEvent` awaiting response is stored."
    connected: asyncio.Event
    "To record the status of the connection."
    ready: asyncio.Event
    "To record whether preparations have been completed"
    clients: list[Identifier]
    "List of id of clients connecting to the server."

    _receiver_task: asyncio.Task[None]

    def __init__(self, id_: Optional[Identifier] = None, timeout: float = 8.0):
        self.timeout = timeout

        self.connected = asyncio.Event()
        self.ready = asyncio.Event()
        self.response_waiters = {}
        self.routes = {}
        self.id_ = id_ or str(uuid4())
        self.clients = []

        super().__init__()

    def route(self, name: Optional[str] = None) -> Callable[[RfT], RfT]:
        """Decorator version of :meth:`.set_route`.

        Args:
            name: The name of a route."""
        def decorator(function: RfT) -> RfT:
            self.set_route(function, name)
            return function
        return decorator

    def set_route(self, function: Route, name: Optional[str] = None) -> None:
        """Set up a Route.
        The configured Route can be executed by the other party.

        Args:
            function: Function for a route.
            name: The name of a route."""
        if name is None:
            name = function.__name__
        self.routes[name] = function

    def delete_route(self, target: Route | str) -> None:
        """Do the opposite of :meth:`.set_route`.

        Args:
            target: Function or name of Route to be deleted

        Raises:
            RouteNotFound: Occurs when a route is not found."""
        for key in list(self.routes.keys()):
            if key == target or self.routes[key] == target:
                del self.routes[key]
                break
        else:
            if not isinstance(target, str):
                target = target.__name__
            raise exceptions.RouteNotFound(target, "Route '%s' was not found" % target)

    async def run_route(self, target: str, *args, **kwargs) -> Any:
        """Execute the registered Route.

        Args:
            target: The name of the route to be run.
            *args: The arguments to be passed to the route.
            *kwargs: The keyword arguments to be passed to the route.

        Raises:
            RouteNotFound: Occurs when a route is not found."""
        if target not in self.routes:
            raise exceptions.RouteNotFound(target, "Route '%s' was not found" % target)

        self.call_event("on_run_route", target, args, kwargs)
        result = self.routes[target](*args, **kwargs)
        if iscoroutine(result):
            result = await result

        return result

    async def _process_request(self, request: RequestPayload) -> ResponsePayload:
        self._check_verified()
        # リクエストを処理します。
        try:
            data = await self.run_route(request["route"], *request["args"], **request["kwargs"])
        except exceptions.RouteNotFound as e:
            logger.warn(f"Route '{request['route']}' which was requested was not found")
            data = ResponsePayload(
                type="response", source=self.id_, target=request["source"],
                session=request["session"], status="Warning", data=(
                    "RouteNotFound", (str(e),)
                )
            )
        except Exception as e:
            logger.error("Ignoring error while running route '%s':\n%s" % (request["route"], format_exc()))
            data = ResponsePayload(
                type="response", source=self.id_, target=request["source"],
                session=request["session"], status="Error", data=(
                    _get_exception_name(e), format_exc()
                )
            )
        else:
            data = ResponsePayload(
                type="response", source=self.id_, target=request["source"],
                session=request["session"], status="Ok", data=data
            )
        # レスポンスを送る。
        await self._send_json(data)

    def is_verified(self) -> bool:
        "Whether the client has been admitted to the server."
        return self.id_ is not None

    def _check_verified(self):
        if self.id_ is None:
            raise exceptions.NotVerified("Not yet accepted as a client by the server.")

    async def request(self, target: Identifier, route: str, *args, **kwargs) -> Any:
        """Make a request to the other party.

        Args:
            target: ID of the client to be sent.
                Alternatively, it can be specified by :class:`ipcs.types_.AutoDecideRouteType`.
            route: The name of the route.
            *args: The arguments to be passed to the route.
            *kwargs: The keyword arguments to be passed to the route.

        Raises:
            ConnectionClosedOnRequest: This occurs when a disconnection occurs during a request.
            TimeoutOnRequest: Occurs when a request times out.
            ExceptionRaisedOnRequest: Occurs when an error occurs at the request destination."""
        self._check_verified()

        session = str(uuid4())
        self.response_waiters[session] = DataEvent()
        request_log = "%s - %s > %s" % (route, session, target)
        logger.info("Prepare request: %s" % request_log)

        # もし送信先が不明の場合はエラーを起こす。
        if target not in self.clients:
            raise exceptions.TargetNotFound("No destination found: %s" % target)

        # リクエストを送る。
        try:
            await self._send_json(sent := RequestPayload(
                type="request", source=self.id_, target=target, session=session,
                route=route, args=args, kwargs=kwargs
            ))
        except ConnectionClosed as e:
            raise exceptions.ConnectionClosed(
                e.code, e.reason, "Request failed because of disconnection."
            )
        self.call_event("on_request", sent)

        # レスポンスを待機する。
        try:
            data = await asyncio.wait_for(
                self.response_waiters[session].wait(),
                timeout=self.timeout
            )
        except asyncio.TimeoutError:
            logger.warn("Timeout request: %s" % session)
            raise exceptions.Timeout("No response was received for the request.")
        del self.response_waiters[session]
        self.call_event("on_response", data)

        # レスポンスをレビューする。
        assert data is not None
        if data["status"] == "Warning":
            raise getattr(exceptions, data["data"][0])(*data["data"][1])
        elif data["status"] == "Error":
            raise exceptions.ExceptionRaised(data["data"][1])
        else:
            logger.info("Successful request: %s" % request_log)
            return data["data"]

    async def _send_json(self, data: Payload) -> None:
        # JSONを送る。
        assert self.ws is not None
        logger.info(">>> %s" % _data_str(data))
        self.call_event("on_send", data)
        await self.ws.send(dumps(data))

    def _when_special(self, data: ResponsePayload) -> None:
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

    async def _receiver(self):
        # サーバーから送られてくるデータを受け取り適切な処理を行います。
        while True:
            data: Payload = loads(await self.ws.recv())
            logger.info("<<< %s" % _data_str(data))

            if data["type"] == "request":
                data: RequestPayload
                asyncio.create_task(
                    self._process_request(data),
                    name=f"ipcs.client.process_request: {data['route']}"
                )
            else:
                data: ResponsePayload
                if data["status"] == "Special":
                    self._when_special(data)
                else:
                    if data["session"] in self.response_waiters:
                        self.response_waiters[data["session"]].set(data)
                    else:
                        # ここは普通実行されてはいけない場所です。もし実行されたのならバグがある可能性があることになる。
                        logger.warn("Unidentified data was sent: %s@%s" % (data["session"], data["source"]), stacklevel=1)

            self.call_event("on_receive", data)

    async def _verify(self):
        # 自分のIDが使用可能か確認したりする。
        await self.ws.recv()
        await self.ws.send(self.id_)
        result = await self.ws.recv()
        if result != "1":
            raise exceptions.VerifyFailed(result)

    @staticmethod
    def _dis_warn(e: Exception, l = logger):
        if isinstance(e, ConnectionClosedOK):
            l.info("It disconnects and reconnects after three seconds: %s" % e)
        else:
            l.warn("It disconnects and reconnects after three seconds: %s" % e)

    async def connect(self, reconnect: bool = True, **kwargs) -> None:
        """Connect to the server.

        Args:
            reconnect: Whether to reconnect
            **kwargs: The keyword arguments to be passed to :func:`websockets.client.connect`.

        Raises:
            VerifyFailed: Occurs when the client is not acknowledged by the server.
                One possible cause is that a client with the same ID has already connected to the server."""
        logger.info("Connecting...")
        async for ws in connect(**kwargs):
            logger.info("Connected")

            # 下準備をする。
            self.connected.set()
            self.call_event("on_connect")
            self.ws = ws
            self.response_waiters = {}

            # 実行する。
            try:
                logger.info("Verifying...")
                await asyncio.wait_for(self._verify(), timeout=self.timeout)
                logger.info("Verified: %s" % self.id_)

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
                        self._dis_warn(e)
                        await asyncio.sleep(3)
                        logger.info("Connecting...")
                        continue
                raise e

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