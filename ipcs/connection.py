# ipcs - Connection

from typing import Any

from abc import ABC, abstractmethod

import asyncio

from orjson import dumps

from .types_ import RequestPayload, ResponsePayload, Id, Session
from .errors import TimeoutError, FailedToProcessError
from .utils import DataRoute, payload_to_str
from .client import AbcClient


__all__ = ("Connection",)


class Connection:
    def __init__(self, client: AbcClient, id_: Id):
        self.client, self.id_ = client, id_
        self.queues: dict[Session, DataRoute[ResponsePayload]] = {}

    async def send(self, route: str, *args: Any, **kwargs: Any) -> Any:
        # データの準備をする。
        session = self.client.generate_session()
        self.queues[session] = DataRoute()
        # 送信する。
        await self.client.send_raw(dumps(payload := RequestPayload(
            source=self.client.id_, target=self.id_, secret=False,
            session=session, route=route, types="request",
            args=args, kwargs=kwargs
        )))
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