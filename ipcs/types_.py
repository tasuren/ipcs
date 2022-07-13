# icps - Types

from typing import TypeAlias, Protocol, TypedDict, Literal, Any
from collections.abc import Sequence


Id: TypeAlias = str
Route: TypeAlias = str
Session: TypeAlias = str


class BasePayload(TypedDict):
    source: Id
    target: Id
    secret: bool
    session: Session
    route: str


class RequestPayload(BasePayload):
    type: Literal["request"]
    args: Sequence[Any]
    kwargs: dict[str, Any]


class ResponsePayload(BasePayload):
    type: Literal["response"]
    status: Literal["ok", "error"]
    result: Any


class WebSocketProtocol(Protocol):

    @property
    def closed(self) -> bool:
        ...

    async def send(self, data: str | bytes, *args: Any, **kwargs: Any) -> None:
        ...

    async def recv(self) -> str | bytes:
        ...

    async def close(self, code: int = 1000, reason: str = "...") -> None:
        ...