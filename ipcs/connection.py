# ipcs - Connection

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import asyncio

from .types_ import RequestPayload, ResponsePayload
from .errors import FailedToProcessError, FailedToRequestError
from .utils import DataEvent, payload_to_str

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

    def __init__(self, client: AbcClient, id_: str) -> None:
        self.client, self.id_ = client, id_
        self.queue: dict[str, DataEvent[ResponsePayload]] = {}

    async def close(self) -> None:
        "Disconnect this connection."
        for key, value in list(self.queue.items()):
            if not value.is_set():
                value.set_with_null()
            del self.queue[key]
        del self.client.connections[self.id_]

    async def request(
        self, route: str, *args: Any,
        ipcs_secret: bool = False,
        **kwargs: Any
    ) -> Any:
        """Make a request to the client connected by this connection.

        Args:
            route: The name of the str you wish to execute at the request destination.
            *args: The arguments to be passed to the str.
            ipcs_secret: Whether the request is for internal use by ipcs.
                Do not set this to True for normal use.
            **kwargs: The arguments to be passed to the str.

        Raises:
            ipcs.errors.FailedToProcessError: Occurs when an error occurs at the connection site.
            ipcs.errors.FailedToRequestError: Occurs when an error occurs while sending a request.
            ipcs.errors.ClosedConnectionError: Occurs when the connection is broken and a request cannot be made."""
        # データの準備をする。
        session = self.client.generate_session()
        self.queue[session] = DataEvent()
        # 送信する。
        self.client.dispatch("on_request", payload := RequestPayload(
            source=self.client.id_, target=self.id_, secret=ipcs_secret,
            session=session, route=route, type="request",
            args=args, kwargs=kwargs
        ))
        # レスポンスを待機する。
        try:
            await self.client._send(payload)
            data = await asyncio.wait_for(self.queue[session].wait(), self.client.timeout)
        except Exception as e:
            del self.queue[session]
            error = FailedToRequestError()
            error.__cause__ = e
            raise error
        else:
            del self.queue[session]
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