# ipcs - Server

from typing import Any

from asyncio import Future

from websockets.exceptions import ConnectionClosed
from websockets.server import serve

from orjson import loads, dumps

from .types_ import WebSocketProtocol, RequestPayload, ResponsePayload
from .utils import payload_to_str
from .connection import Connection
from .client import AbcClient, logger


__all__ = ("ConnectionForServer", "Server")


class ConnectionForServer(Connection):
    """Class that extends :class:`Connection` for :class:`Server`.

    Args:
        ws: This is the websocket to the client connected by this connection."""

    ws: WebSocketProtocol
    "This is the websocket to the client connected by this connection."

    async def close(self) -> None:
        await super().close()
        if not self.client._closing and not self.ws.closed:
            await self.ws.close(self.client._code, self.client._reason) # type: ignore


class Server(AbcClient[ConnectionForServer | Connection]):
    """Server for ipcs communication.
    This is not normally used to run ipcs servers. Instead, use ``ipcs-server``, which is available on the command line.
    This command is automatically set up during installation with pip."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.connections[self.id_] = Connection(self, self.id_)

    async def communicate(self, ws: WebSocketProtocol) -> None:
        """Function called when a new client connects.
        Used internally.
        ipcs uses web sockets using a third-party library called websocekts, but if you want to use another web socket library, pass the newly connected web socket to this function.
        However, since the websockets available to ipcs must conform to :class:`ipcs.types_.WebSocketProtocol`, you will need to wrap the websocket class to make it conform to :class:`ipcs.types_.WebSocketProtocol` if it differs from that.

        Args:
            ws: The websocket of the newly connected client."""
        # 認証を行う。
        id_ = (await ws.recv())[7:]
        assert isinstance(id_, str)
        if id_ in self.connections:
            await ws.send("error")
            return await ws.close(1008, "ID is not appropriate.")
        self.connections[id_] = ConnectionForServer(self, id_)
        self.connections[id_].ws = ws # type: ignore
        await ws.send(dumps(list(self.connections.keys())))
        # メインプロセスを実行する。
        self.loop.create_task(
            self.request_all("on_connect", id_, ipcs_secret=True),
            name="ipcs: Request on_connect secret request: %s" % id_
        )
        self.dispatch("on_connect", id_)
        try:
            while True:
                data: RequestPayload | ResponsePayload = loads(await ws.recv())
                if data["target"] == self.id_:
                    self._on_receive(data)
                else:
                    self._transfer_data(data)
        except ConnectionClosed:
            await self._close_connection(id_)
            self.loop.create_task(
                self.request_all("on_disconnect", id_, ipcs_secret=True),
                name="ipcs: Request on_disconnect secret request: %s" % id_
            )
            self.dispatch("on_disconnect", id_)

    async def _send(self, data: RequestPayload | ResponsePayload) -> None:
        if data["target"] == self.id_:
            self._on_receive(data)
        else:
            self._transfer_data(data)

    def _transfer_data(self, data: RequestPayload | ResponsePayload) -> None:
        # 渡されたデータをそのデータで指定されている宛先に送信します。
        for connection in self.connections.values():
            if connection.id_ == data["target"]:
                logger.info("Transfer data: %s" % payload_to_str(data))
                self.loop.create_task(
                    connection.ws.send(dumps(data)), # type: ignore
                    name="ipcs: Pass data: %s" % data["session"]
                )
                break
        else:
            logger.warning("I tried to transfer data but could not find a destination: %s" % payload_to_str(data))

    async def start(self, *args: Any, **kwargs: Any) -> None:
        """Run the server.

        Args:
            *args: The arguments to be passed to ``serve`` in the third party library websockets.
                Details of ``serve`` in `here <https://websockets.readthedocs.io/en/stable/reference/server.html#websockets.server.serve>`_.
            **kwargs: The keyword arguments to be passed to ``serve`` in the third party library websockets.
                Details of ``serve`` in `here <https://websockets.readthedocs.io/en/stable/reference/server.html#websockets.server.serve>`_."""
        await super().start()
        for_loop = Future[None]()
        async with serve(self.communicate, *args, **kwargs): # type: ignore
            await for_loop

    async def close(self, code: int = 1000, reason: str = "...") -> None:
        """Terminate the server.

        Args:
            code: This code is used when cutting with a websocket.
            reason: This reason is used when cutting with a websocket."""
        self._code, self._reason = code, reason
        await super().close(code, reason)