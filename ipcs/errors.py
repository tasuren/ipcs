# ipcs - Errors

from typing import Any


__all__ = (
    "IpcsError", "IdIsNotFound", "RequestError", "FailedToRequestError",
    "FailedToProcessError", "ClosedConnectionError"
)


class IpcsError(Exception):
    "All errors defined in ipcs are inherited errors."


class IdIsNotFound(IpcsError):
    "This error occurs when str is not found."


class RequestError(IpcsError):
    "This error occurs when a request fails."
class FailedToRequestError(RequestError):
    """This error occurs when a request failes at client.
    What error occurred goes into the attribute `__cause__`.
    Example: `asyncio.TimeoutError`"""

    __cause__: Exception
class FailedToProcessError(RequestError):
    """Occurs when an error occurs at the request destination.

    Attributes:
        error: The name and description of the error that occurred at the request destination.
            The format is ``<name>: <content>``."""

    def __init__(self, message: str, error: str, *args: Any, **kwargs: Any) -> None:
        super().__init__(message, *args, **kwargs)
        self.error = error
class ClosedConnectionError(RequestError):
    "This occurs when a request is attempted but communication is lost."