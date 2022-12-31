# icps - Types

from typing import TypeAlias, Protocol, TypedDict, Literal, Any
from collections.abc import Sequence


__all__ = (
    "BasePayload", "RequestPayload",
    "ResponsePayload", "WebSocketProtocol"
)


class BasePayload(TypedDict):
    "The base JSON type of the raw data used for communication."

    source: str
    "The ID of the data source."
    target: str
    "The ID of the destination of the data."
    secret: bool
    "It is whether the data is directed to the inside of ipcs or not."
    session: str
    "str ID to identify data."
    route: str
    "str Name."


class RequestPayload(BasePayload):
    "The JSON type of the raw data at the time of the request."

    type: Literal["request"]
    "Indicates the type of data."
    args: Sequence[Any]
    "Arguments to be passed to str."
    kwargs: dict[str, Any]
    "Keyword arguments to be passed to str."


class ResponsePayload(BasePayload):
    "The JSON type of the raw data at response time."

    type: Literal["response"]
    "Indicates the type of data."
    status: Literal["ok", "error"]
    "A string representing the result of the request execution."
    result: Any
    """Stores the results of the request execution.
    If there is an error, this will contain a string with the name of the error and its contents."""


class WebSocketProtocol(Protocol):
    "Protocol class to indicate functions that must be implemented in the class for WebSocket communication used within ipcs."

    @property
    def closed(self) -> bool:
        "Returns whether the websocket is closed or not."
        ...

    async def send(self, data: Any, *args: Any, **kwargs: Any) -> None:
        "Sends data via websockets."

    async def recv(self) -> Any:
        "Receives data via websockets."

    async def close(self, code: int = 1000, reason: str = "...") -> None:
        "Disconnect the web socket."