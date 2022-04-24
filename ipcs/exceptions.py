# ipcs - Exceptions


__all__ = (
    "IpcsException", "RouteNotFound", "NotVerified", "VerifyFailed",
    "EventFunctionNotFound", "ExceptionOnRequest", "TargetNotFound",
    "Timeout", "ExceptionRaised", "ConnectionClosed"
)


class IpcsException(Exception):
    "Base exception of Ipcs' exception."


class RouteNotFound(IpcsException):
    "Occurs when Route is not found."

    route: str
    "Name of route that was not found."

    def __init__(self, route: str, *args, **kwargs):
        self.route = route
        super().__init__(*args, **kwargs)


class EventFunctionNotFound(IpcsException):
    "Occurs when Event Function is not found."

    event: str
    "Name of event that was not found."

    def __init__(self, event: str, *args, **kwargs):
        self.event = event
        super().__init__(*args, **kwargs)


class NotVerified(IpcsException):
    "Occurs when Ipc is not verified."


class VerifyFailed(IpcsException):
    "Occurs when Ipc is not verified."


class ExceptionOnRequest(IpcsException):
    "Occurs when a error occurs while processing a request."


class TargetNotFound(ExceptionOnRequest):
    "Occurs when the destination cannot be found."


class Timeout(ExceptionOnRequest):
    "Occurs when a request is made but no response is received for long time."


class ExceptionRaised(ExceptionOnRequest):
    "Occurs when an error occurs on the other side during the request."


class ConnectionClosed(ExceptionOnRequest):
    "Occurs when client is disconnected from server while requesting."

    def __init__(self, code: int, reason: str, *args, **kwargs):
        self.code, self.reason = code, reason
        super().__init__(*args, **kwargs)