# ipcs - Errors


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
    ...
class ClosedConnectionError(RequestError):
    ...