# ipcs - Utils

from typing import TypeVar, Generic

from asyncio import Event as AsyncioEvent

from .types_ import RequestPayload, ResponsePayload
from .errors import ClosedConnectionError


__all__ = ("SimpleAttrDict", "DataEvent", "payload_to_str")


ValueT = TypeVar("ValueT")
class SimpleAttrDict(dict[str, ValueT]):
    """This class is a dictionary that allows values to be retrieved from attributes.
    Note, however, that dictionaries retrieved from attributes cannot be accessed from attributes."""

    def __getattr__(self, key: str) -> ValueT:
        if key in self:
            return self[key]
        raise AttributeError(key)


DataT = TypeVar("DataT")
class DataEvent(AsyncioEvent, Generic[DataT]):
    "This class extends the ``Event`` class of the standard asyncio library to allow setting some object."

    data: DataT | None = None
    null = False

    def clear(self) -> None:
        self.data = None
        self.null = False
        return super().clear()

    def set_with_null(self) -> None:
        """Runs :meth:`.set` but does not set any data.
        In this case, :meth:`.wait` raises a :class:`ClosedConnectionError`."""
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


def payload_to_str(payload: RequestPayload | ResponsePayload) -> str:
    "Represents raw data as a string."
    return "<Payload from={} to={} type={} route={} session={}>".format(
        payload['source'], payload['target'], payload['type'],
        payload['route'], payload['session']
    )


def error_to_str(error: Exception) -> str:
    """Error to a string like name and content.
    The format is ``<name>: <content>``."""
    return f"{error.__class__.__name__}: {error}"