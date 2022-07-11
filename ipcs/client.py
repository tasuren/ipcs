# ipcs - Client

from typing import Any

from abc import ABC, abstractmethod


class AbcClient(ABC):
    @abstractmethod
    async def send(self, event: str, *args, **kwargs) -> Any:
        ...

    def listen(self, event: str) -> Callable[]: