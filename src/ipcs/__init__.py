__all__ = (
    "__version__", "Request", "AbcClient", "Client", "logger",
    "Connection", "Server", "ConnectionForServer", "IpcsError", "IdIsNotFound",
    "RequestError", "FailedToProcessError", "ClosedConnectionError",
    "logger"
)

from logging import getLogger

from .connection import Connection
from .server import *
from .client import *
from .server import *
from .errors import *


__version__ = "0.2.0"
"The version of icps."


logger = getLogger(__name__)
"Log output destination. ipcs use logging from the standard library."