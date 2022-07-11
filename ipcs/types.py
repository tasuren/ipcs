# icps - Types

from typing import TypeAlias, TypedDict, Literal, Any
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
    types: Literal["request"]
    args: Sequence[Any]
    kwargs: dict[str, Any]


class ResponsePayload(BasePayload):
    types: Literal["response"]
    status: Literal["ok", "error"]
    result: Any