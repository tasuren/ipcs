# ipcs - Base

from __future__ import annotations

from typing import TypeVar, Optional, Any
from collections.abc import Callable

from logging import getLogger, Logger
from traceback import format_exc

from collections import defaultdict
from uuid import uuid4
import asyncio

from websockets.exceptions import ConnectionClosed, ConnectionClosedOK

from .types_ import Route, EventFunction, Identifier, Payload, RequestPayload, ResponsePayload
from .utils import DataEvent, _get_exception_name, _data_str
from . import exceptions


__all__ = ("IpcsClientBase", "EventManager", "RouteManager")


EfT = TypeVar("EfT", bound=EventFunction)
class EventManager:
    """This class is used for calling events.
    The :ref:`Event Reference<event_reference>` describes the events that are included in the standard."""

    listeners: defaultdict[str, list[EventFunction]]
    "This dictionary contains event functions."

    def __init__(self):
        self.listeners = defaultdict(list)

    def call_event(self, event: str, *args, **kwargs) -> None:
        """Calls up a registered event.
        Events can be registered with :meth:`.listen_event`.

        Args:
            event: The name of the event.
            *args: The arguments to be passed to the event function.
            *kwrags: The keyword arguments to be passed to the event function."""
        for function in self.listeners[event]:
            result = function(*args, **kwargs)
            if asyncio.iscoroutine(result):
                asyncio.create_task(result, name=f"ipcs.client.call_event: {event}")

    def listen(self, name: Optional[str] = None) -> Callable[[EfT], EfT]:
        """Decorator version of :meth:`.listen_event`.

        Args:
            name: The name of the event.
                If not specified, the function name is used."""
        def decorator(function: EfT) -> EfT:
            self.listen_event(function, name)
            return function
        return decorator

    def listen_event(self, function: EventFunction, name: Optional[str] = None) -> None:
        """Register event functions.

        Args:
            function: The name of the function.
            name: The name of the event.
                If not specified, the function name is used."""
        if name is None:
            name = function.__name__
        self.listeners[name].append(function)

    def unlisten_event(self, target: EventFunction | str) -> None:
        """Deletes a registered event function.

        Args:
            target: The function or name to unregister.

        Raises:
            EventFunctionNotFound: If the function is not found."""
        for event in list(self.listeners.keys()):
            if event == target:
                del self.listeners[event]
                break
            elif not isinstance(target, str) and target in self.listeners[event]:
                self.listeners[event].remove(target)
                break
        else:
            if not isinstance(target, str):
                target = target.__name__
            raise exceptions.EventFunctionNotFound(
                "Event Function '%s' not found" % target
            )


RfT = TypeVar("RfT", bound=Route)
class RouteManager:
    "This class is used to manage Route."

    routes: dict[str, Route]
    "The number of seconds to time out."

    def __init__(self):
        self.routes = {}

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

        result = self.routes[target](*args, **kwargs)
        if asyncio.iscoroutine(result):
            result = await result

        return result


class IpcsClientBase(EventManager, RouteManager):
    """This is the base class for Ipcs clients.

    Args:
        id_: ID for client identification
        timeout: Seconds until request times out"""

    id_: Identifier
    "An identification ID that indicates who you are in ipc communication."
    timeout: float
    "The Route is stored here."
    response_waiters: dict[str, DataEvent[ResponsePayload]]
    "This is where the :class:`DataEvent` awaiting response is stored."

    _receiver_task: asyncio.Task[None]
    _logger = getLogger("ipcs")

    def __init__(self, id_: Optional[Identifier] = None, timeout: float = 8.0):
        self.timeout = timeout

        self.connected = asyncio.Event()
        self.ready = asyncio.Event()
        self.response_waiters = {}
        self.id_ = id_ or str(uuid4())

        super().__init__()
        super(EventManager, self).__init__()

    def is_verified(self) -> bool:
        "Whether the client has been admitted to the server."
        return self.id_ is not None

    def _check_verified(self):
        if self.id_ is None:
            raise exceptions.NotVerified("Not yet accepted as a client by the server.")

    def check(self, target: Identifier) -> None:
        """Function called to check if the request is appropriate.

        Args:
            target: The ID to which the request is sent."""

    async def request(self, target: Identifier, route: str, *args, **kwargs) -> Any:
        """Make a request to the other party.

        Args:
            target: ID of the client to be sent.
            route: The name of the route.
            *args: The arguments to be passed to the route.
            *kwargs: The keyword arguments to be passed to the route.

        Raises:
            ConnectionClosed: This occurs when a disconnection occurs during a request.
            Timeout: Occurs when a request times out.
            ExceptionRaised: Occurs when an error occurs at the request destination.
            TargetNotFound: Occurs when the destination of the request cannot be found.

        Notes:
            It is also possible to make requests to the server.
            The ID of the server is ``__IPCS_SERVER__``."""
        if target == self.id_:
            raise ValueError("You cannot send it to yourself.")
        self._check_verified()

        session = str(uuid4())
        self.response_waiters[session] = DataEvent()
        request_log = "%s - %s > %s" % (route, session, target)
        self._logger.info("Prepare request: %s" % request_log)

        self.check(target)

        # リクエストを送る。
        try:
            await self.send_json(sent := RequestPayload(
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
            self._logger.warning("Timeout request: %s" % session)
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
            self._logger.info("Successful request: %s" % request_log)
            return data["data"]

    async def _process_request(self, request: RequestPayload) -> ResponsePayload:
        self._check_verified()
        # リクエストを処理します。
        try:
            data = await self.run_route(request["route"], *request["args"], **request["kwargs"])
        except exceptions.RouteNotFound as e:
            self._logger.warning(f"Route '{request['route']}' which was requested was not found")
            data = ResponsePayload(
                type="response", source=self.id_, target=request["source"],
                session=request["session"], status="Warning", data=(
                    "RouteNotFound", (e.route, str(e))
                )
            )
        except Exception as e:
            self._logger.error("Ignoring error while running route '%s':\n%s" % (request["route"], format_exc()))
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
        await self.send_json(data)

    def _when_special(self, data: ResponsePayload) -> None:
        ...

    def on_receive(self, data: Payload):
        """Function that should be called when data is received.

        Args:
            data: Data which was received."""
        self._logger.info("<<< %s" % _data_str(data))

        if data["type"] == "request":
            # data: RequestPayload
            asyncio.create_task(
                self._process_request(data), # type: ignore
                name=f"ipcs.client.process_request: {data['route']}" # type: ignore
            )
        else:
            # data: ResponsePayload
            if data["status"] == "Special": # type: ignore
                self._when_special(data) # type: ignore
            else:
                if data["session"] in self.response_waiters:
                    self.response_waiters[data["session"]].set(data) # type: ignore
                else:
                    # ここは普通実行されてはいけない場所です。もし実行されたのならバグがある可能性があることになる。
                    self._logger.warning("Unidentified data was sent: %s@%s" % (data["session"], data["source"]), stacklevel=1)

        self.call_event("on_receive", data)

    async def send_json(self, data: Payload) -> None:
        """Send JSON to WebSocket.
        This is used internally and md not normally called from the outside.

        Args:
            data: Data to be sent."""
        raise NotImplementedError()

    @staticmethod
    def _dis_warn(e: Exception, l: Logger):
        if isinstance(e, ConnectionClosedOK):
            l.info("It disconnects and reconnects after three seconds: %s" % e)
        else:
            l.warning("It disconnects and reconnects after three seconds: %s" % e)