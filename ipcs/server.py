# ipcs - Server

from typing import Any

from .types_ import WebSocketProtocol
from .connection import Connection
from .client import AbcClient


class ConnectionForServer(Connection):
    ws: WebSocketProtocol

    def __init__(self, ws: WebSocketProtocol, *args: Any, **kwargs: Any) -> None:
        self.ws = ws
        super().__init__(*args, **kwargs)