# ipcs - Utils

from typing import TypeVar, Generic, Optional

from asyncio import Event

from .types_ import Payload


__all__ = ("DataEvent",)


DataT = TypeVar("DataT")
class DataEvent(Event, Generic[DataT]):
    "Extends :class:`asyncio.Event` to allow storing data."

    data: Optional[DataT] = None

    def set(self, data: DataT) -> None: # type: ignore
        self.data = data
        return super().set()

    def clear(self) -> None:
        self.data = None
        return super().clear()

    async def wait(self) -> Optional[DataT]: # type: ignore
        await super().wait()
        return self.data


def _get_exception_name(error: Exception) -> str:
    return f"{error.__class__.__name__}: {error}"


def _data_str(data: Payload) -> str:
    return f"{data['type']} - {data['source']} > {data['session']} > {data['target']}"