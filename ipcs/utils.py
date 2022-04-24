# ipcs - Utils

from typing import TypeVar, Generic, Optional
from collections.abc import Callable

from collections import defaultdict
import asyncio

from .exceptions import EventFunctionNotFound
from .types_ import Payload, EventFunction


__all__ = ("DataEvent", "EventManager")


DataT = TypeVar("DataT")
class DataEvent(asyncio.Event, Generic[DataT]):

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


EfT = TypeVar("EfT", bound=EventFunction)
class EventManager:
    "This class is used for calling events."

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
            raise EventFunctionNotFound(
                "Event Function '%s' not found" % target
            )