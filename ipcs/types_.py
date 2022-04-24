# ipcs - Types

from typing import TypeAlias, TypedDict, Literal, Any
from collections.abc import Callable, Coroutine, Sequence

from enum import Enum


__all__ = (
    "Route", "Identifier", "AutoDecideRouteType",
    "Payload", "RequestPayload", "ResponsePayload"
)


Route: TypeAlias = Callable[..., Any | Coroutine]
"Alias for Route type"
EventFunction: TypeAlias = Route
"Alias for :var:`Route`."
Identifier: TypeAlias = str
"Alias for Identifier of icp Client"
Session: TypeAlias = str
"Alias for Session of request/response data."


class AutoDecideRouteType(Enum):
    "The type of how to determine which client to send the request to when no request destination is specified."

    ALL = 0
    """Send all client request.
    No value will be returned."""
    RANDOM = 1
    "Send client which was choiced by server request"


class Payload(TypedDict):
    """This is the base of the type of data to be sent and received.
    Normally, this class is not used by you."""

    type: Literal["request", "response"]
    "The type of data content."
    source: str
    """An identification ID to identify which ipc client the data is from.
    For servers, it is ``"0"``."""
    target: Identifier | None
    """Destination identification ID.
    If set to ``None``, the server will automatically determine the destination."""
    session: Session
    "Session ID to identify from which request the data came."


class RequestPayload(Payload):
    "The type of the data in the request."

    route: str
    "The name of the Route to execute at the request destination."
    # Main Data
    args: Sequence[Any]
    "Arguments to be passed to the Route to be executed at the request destination."
    kwargs: dict[str, Any]
    "Keyword arguments to be passed to the Route to be executed at the request destination."


class ResponsePayload(Payload):
    "The type of the data in the response."

    status: Literal["Ok", "Warning", "Error", "Special"]
    """This is the result of executing Route at the request destination.
    For messages sent from the server, it will be ``Special``."""
    data: Any
    """The value returned when Route is executed at the request destination.
    If :attr:`.status` is ``Error``, it is the error string."""