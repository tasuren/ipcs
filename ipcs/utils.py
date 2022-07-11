# ipcs - Utils

from typing import TypeVar, Generic

from asyncio import Route as AsyncioRoute

from .types import BasePayload


__all__ = ("SimplAttrDict", "DataRoute", "payload_to_str")


ValueT = TypeVar("ValueT")
class SimpleAttrDict(dict[str, ValueT]):
    def __getattr__(self, key: str) -> ValueT:
        if key in self:
            return self[key]
        raise AttributeError(key)


DataT = TypeVar("DataT")
class DataRoute(AsyncioRoute, Generic[DataT]):

    data: DataT | None = None

    def clear(self) -> None:
        self.data = None
        return super().clear()

    def set(self, data: DataT) -> None:
        self.data = data
        return super().set()

    async def wait(self) -> DataT:
        await super().wait()
        return self.data


def payload_to_str(payload: BasePayload) -> str:
    return f"<from={payload['source']}, to={payload['target']}, route={payload['route']}, session={payload['session']}>"


def error_to_str(error: Exception) -> str:
    return f"{error.__class__.__name__}: {error}"