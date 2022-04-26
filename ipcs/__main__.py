# Icps - Main

from argparse import ArgumentParser
import logging

try:
    from ipcs import __version__, IpcsServer
except ImportError:
    from sys import path as spath
    spath.insert(0, __file__[:-17])
    from ipcs import __version__, IpcsServer
from ipcs.server import logger


logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("[%(name)s] [%(levelname)s] %(message)s"))
logger.addHandler(handler)


def main():
    parser = ArgumentParser()
    parser.add_argument("--host", default="localhost", help="Host Name")
    parser.add_argument("--port", default=8080, help="Port", type=int)
    parser.add_argument("--version", action="store_true", help="Version")
    args = parser.parse_args()


    if args.version:
        print(__version__)
    else:
        logger.info(f"ipcs v{__version__}")
        logger.info("Host: %s, Port: %s" % (args.host, args.port))
        server = IpcsServer()

        @server.route()
        def ping():
            return "pong"

        @server.route("print")
        def print_(*args, **kwargs):
            print(*args, **kwargs)

        server.run(host=args.host, port=args.port)
        logger.info("Bye")


if __name__ == "__main__":
    main()