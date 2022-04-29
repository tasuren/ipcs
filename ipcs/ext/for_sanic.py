# ipcs - For Sanic

from __future__ import annotations

from typing import TYPE_CHECKING

from websockets.connection import CLOSED

from ..server import IpcsServer

if TYPE_CHECKING:
    from sanic.server.websockets.impl import WebsocketImplProtocol


__all__ = ("SanicIpcsServer",)


class SanicIpcsServer(IpcsServer):
    """This is a class that makes :class:`IpcsServer` usable with WebSocket of the web framework Sanic.
    You can use Sanic's `websocket` decorator to create a connection to IpcsServer by passing a WebSocket to :meth:`SanicIpcsServer.communicate`, and then use the :class:`IpcsServer` to create a connection to IpcsServer.
    At the end of Sanic, call :meth:`SanicIpcsServer.close`."""

    def is_ws_closed(self, ws: WebsocketImplProtocol) -> bool: # type: ignore
        return ws.connection.state == CLOSED

    async def communicate(self, ws: WebsocketImplProtocol) -> None: # type: ignore
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