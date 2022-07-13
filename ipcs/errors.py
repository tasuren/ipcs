# ipcs - Errors

from typing import Any


__all__ = (
    "IpcsError", "RouteIsNotFound", "RequestError", "TimeoutError",
    "FailedToProcessError", "ClosedConnectionError"
)


class IpcsError(Exception):
    ...


class RouteIsNotFound(IpcsError):
    ...


class RequestError(IpcsError):
    ...
class TimeoutError(RequestError):
    ...
class FailedToProcessError(RequestError):
    def __init__(self, message: str, error: Exception, *args: Any, **kwargs: Any):
        super().__init__(message, *args, **kwargs)
        self.error = error
class ClosedConnectionError(RequestError):
    ...