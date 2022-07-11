# ipcs - Errors


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