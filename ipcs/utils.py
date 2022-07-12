# ipcs - Utils

from typing import TypeVar, Generic

from asyncio import Event as AsyncioEvent

from .types_ import BasePayload
from .errors import ClosedConnectionError


__all__ = ("SimplAttrDict", "DataRoute", "payload_to_str")


ValueT = TypeVar("ValueT")
class SimpleAttrDict(dict[str, ValueT]):
    def __getattr__(self, key: str) -> ValueT:
        if key in self:
            return self[key]
        raise AttributeError(key)


DataT = TypeVar("DataT")
class DataRoute(AsyncioEvent, Generic[DataT]):

    data: DataT | None = None
    null = False

    def clear(self) -> None:
        self.data = None
        self.null = False
        return super().clear()

    def set_with_null(self) -> None:
        self.null = True
        return super().set()

    def set(self, data: DataT) -> None: # type: ignore
        self.data = data
        return super().set()

    async def wait(self) -> DataT: # type: ignore
        await super().wait()
        if self.null:
            raise ClosedConnectionError(
                "The request response could not be received because the connection was terminated."
            )
        return self.data # type: ignore


def payload_to_str(payload: BasePayload) -> str:
    return f"<from={payload['source']}, to={payload['target']}, route={payload['route']}, session={payload['session']}>"


def error_to_str(error: Exception) -> str:
    return f"{error.__class__.__name__}: {error}"