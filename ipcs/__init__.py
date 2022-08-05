# ipcs

from .connection import Connection
from .server import *
from .client import *
from .server import *
from .errors import *


__all__ = (
    "__version__", "__author__", "Request", "AbcClient", "Client", "logger",
    "Connection", "Server", "ConnectionForServer", "IpcsError", "RouteIsNotFound",
    "RequestError", "TimeoutError", "FailedToProcessError", "ClosedConnectionError"
)


__version__ = "0.1.0b3"
"The version of icps."
__author__ = "tasuren"
"The name of the ipcs' author."