# ipcs

from .connection import Connection
from .server import *
from .client import *
from .server import *
from .errors import *


__all__ = (
    "__version__", "Request", "AbcClient", "Client", "logger",
    "Connection", "Server", "ConnectionForServer", "IpcsError", "IdIsNotFound",
    "RequestError", "FailedToProcessError", "ClosedConnectionError"
)


__version__ = "0.1.0rc0"
"The version of icps."