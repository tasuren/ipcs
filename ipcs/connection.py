# ipcs - Connection

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import asyncio

from .types_ import RequestPayload, ResponsePayload, Id, Session
from .errors import TimeoutError, FailedToProcessError
from .utils import DataRoute, payload_to_str

if TYPE_CHECKING:
    from .client import AbcClient


__all__ = ("Connection",)


class Connection:
    """This class is used to represent the connection to the client.
    Requests to the client can be made using this.

    Args:
        client: This is the client who established this connection.
        id_: The ID of the client connected to this connection.

    Attributes:
        client: This is the client who established this connection.
        id_: The ID of the client connected to this connection."""

    def __init__(self, client: AbcClient, id_: Id):
        self.client, self.id_ = client, id_
        self.queues: dict[Session, DataRoute[ResponsePayload]] = {}

    async def close(self) -> None:
        "Disconnect this connection."
        for key, value in list(self.queues.items()):
            if not value.is_set():
                value.set_with_null()
            del self.queues[key]
        del self.client.connections[self.id_]

    async def request(
        self, route: str, *args: Any,
        ipcs_secret: bool = False,
        **kwargs: Any
    ) -> Any:
        """Make a request to the client connected by this connection.

        Args:
            route: The name of the Route you wish to execute at the request destination.
            *args: The arguments to be passed to the Route.
            ipcs_secret: Whether the request is for internal use by ipcs.
                Do not set this to True for normal use.
            **kwargs: The arguments to be passed to the Route."""
        # データの準備をする。
        session = self.client.generate_session()
        self.queues[session] = DataRoute()
        # 送信する。
        self.client.dispatch("on_request", payload := RequestPayload(
            source=self.client.id_, target=self.id_, secret=ipcs_secret,
            session=session, route=route, type="request",
            args=args, kwargs=kwargs
        ))
        await self.client._send(payload)
        # レスポンスを待機する。
        try:
            data = await asyncio.wait_for(self.queues[session].wait(), self.client.timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(payload_to_str(payload))
        # レスポンスを返す。必要に応じてエラーを発生させる。
        if data["status"] == "ok":
            return data["result"]
        else:
            raise FailedToProcessError(
                "The request was not processed because an error occurred on the other end: %s" % data["result"],
                data["result"]
            )

    def __str__(self) -> str:
        return f"<Connection id={self.id_}>"