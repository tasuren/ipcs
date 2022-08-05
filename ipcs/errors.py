# ipcs - Errors

from typing import Any


__all__ = (
    "IpcsError", "RouteIsNotFound", "RequestError", "TimeoutError",
    "FailedToProcessError", "ClosedConnectionError"
)


class IpcsError(Exception):
    "All errors defined in ipcs are inherited errors."


class RouteIsNotFound(IpcsError):
    "This error occurs when Route is not found."


class RequestError(IpcsError):
    "This error occurs when a request fails."
class TimeoutError(RequestError):
    "This error occurs when a request times out."
class FailedToProcessError(RequestError):
    """Occurs when an error occurs at the request destination.

    Attributes:
        error: The name and description of the error that occurred at the request destination.
            The format is ``<name>: <content>``."""

    def __init__(self, message: str, error: str, *args: Any, **kwargs: Any):
        super().__init__(message, *args, **kwargs)
        self.error = error
class ClosedConnectionError(RequestError):
    "This occurs when a request is attempted but communication is lost."