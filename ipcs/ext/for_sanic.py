# ipcs Ext - For Sanic

from typing import Any

from asyncio import all_tasks

from sanic import Websocket
from websockets.connection import CLOSED

from ..server import Server


__all__ = ("ServerForSanic",)


class SanicWebSocketWrapper:
    def __init__(self, real_ws: Websocket):
        self.real_ws = real_ws
        self.send = self.real_ws.send
        self.recv = self.real_ws.recv
        self.close = self.real_ws.close

    @property
    def closed(self) -> bool:
        return self.real_ws.connection.state == CLOSED


class ServerForSanic(Server):
    """Server class for WebSocket support for the `Sanic <https://sanic.dev/>`_ web framework.
    When a websocket connection is made, an instance of that websocket class can be passed to the :meth:`ServerForSanic.communicate` function.

    Notes:
        Currently Sanic's websockets are unable to detect disconnections, so the connection remains in the server class instance after disconnection.
        However, you can relax a bit. You can check to see if the connection is still in use by checking if ``connection.ws.closed`` returns ``True``.
        And because of that, :meth:`ServerForSanic.communicate` is made so that when you reconnect, the connection whose ``closed`` returns ``False`` is deleted before the connection goes through."""

    _code = 1000
    _reason = "..."

    async def communicate(self, ws: Websocket) -> None: # type: ignore
        for connection in list(self.connections.values()):
            if hasattr(connection, "ws") and connection.ws.closed: # type: ignore
                await connection.close()
        return await super().communicate(SanicWebSocketWrapper(ws)) # type: ignore

    async def close(self, *args: Any, **kwargs: Any) -> None:
        for task in all_tasks():
            if "WebsocketFrameAssembler" in str(task.get_coro()):
                if not task.done():
                    task.cancel("Close")
        return await super().close(*args, **kwargs)