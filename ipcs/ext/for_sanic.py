# ipcs - For Sanic

from __future__ import annotations

from typing import TYPE_CHECKING

from asyncio import all_tasks

from websockets.connection import CLOSED

from ..server import IpcsServer

if TYPE_CHECKING:
    from sanic.server.websockets.impl import WebsocketImplProtocol


__all__ = ("SanicIpcsServer",)


class SanicIpcsServer(IpcsServer):
    """This is a class that makes :class:`IpcsServer` usable with WebSocket of the web framework Sanic.
    You can use Sanic's `websocket` decorator to create a connection to IpcsServer by passing a WebSocket to :meth:`SanicIpcsServer.communicate`, and then use the :class:`IpcsServer` to create a connection to IpcsServer.
    At the end of Sanic, call :meth:`SanicIpcsServer.close`.

    Args:
        timeout: The number of seconds to wait for response.

    Warnings:
        The argument ``ignore_verify`` of the constructor of the parent class :class:`IpcsServer` is ``True``.
        I don't know why, but Sanic doesn't notify me of WebSocket disconnections, so I can't detect a disconnect and remove the ID from the list of currently connected clients.
        In this case, when the client reconnects, the ID is still there, so it is covered and the verification fails.
        This is the countermeasure for it."""

    def __init__(self, timeout: float = 8.0):
        super().__init__(timeout, True)

    def is_ws_closed(self, ws: WebsocketImplProtocol) -> bool: # type: ignore
        return ws.connection.state == CLOSED

    async def communicate(self, ws: WebsocketImplProtocol) -> None: # type: ignore
        """Register Sanic's WebSocket with IpcsServer.

        Args:
            ws: WebSocket"""
        return await super().communicate(ws) # type: ignore

    async def start(self, **_) -> None:
        "This is not implemented. Use :meth:`SanicIpcsServer.communicate`."
        self.run()

    async def serve(self, **_) -> None:
        "This is not implemented. Use :meth:`SanicIpcsServer.communicate`."
        self.run()

    def run(self, **_) -> None:
        "This is not implemented. Use :meth:`SanicIpcsServer.communicate`."
        raise NotImplementedError("Use `.communicate`.")

    async def close(self, *args, **kwargs) -> None:
        for task in all_tasks():
            if "WebsocketFrameAssembler" in str(task.get_coro()):
                if not task.done():
                    task.cancel("Close")
        return await super().close(*args, **kwargs)