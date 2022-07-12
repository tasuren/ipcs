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
    def __init__(self, client: AbcClient, id_: Id):
        self.client, self.id_ = client, id_
        self.queues: dict[Session, DataRoute[ResponsePayload]] = {}

    async def close(self) -> None:
        for key, value in list(self.queues.items()):
            if not value.is_set():
                value.set_with_null()
            del self.queues[key]

    async def request(
        self, route: str, *args: Any,
        ipcs_secret: bool = False,
        **kwargs: Any
    ) -> Any:
        # データの準備をする。
        session = self.client.generate_session()
        self.queues[session] = DataRoute()
        # 送信する。
        self.client.dispatch("on_request", payload := RequestPayload(
            source=self.client.id_, target=self.id_, secret=ipcs_secret,
            session=session, route=route, types="request",
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
                "The request was not processed because an error occurred on the other end: <payload=%s, error=%s>"
                    % (payload_to_str(payload), data["result"])
            )