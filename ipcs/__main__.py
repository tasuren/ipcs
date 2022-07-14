# ipcs - Main

from argparse import ArgumentParser
import logging

try:
    from ipcs import __version__, Server, Request
    from ipcs.client import logger
except ImportError:
    from sys import path as spath
    spath.insert(0, __file__[:-17])
    from ipcs import __version__, Server, Request
    from ipcs.client import logger


logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("[%(name)s] [%(levelname)s] %(message)s"))
logger.addHandler(handler)


def main():
    parser = ArgumentParser()
    parser.add_argument("--host", default="localhost", help="Host Name")
    parser.add_argument("--port", default=8080, help="Port", type=int)
    parser.add_argument("--server-id", default="__IPCS_SERVER__", help="Client ID of the server.")
    parser.add_argument("--version", action="store_true", help="Version")
    args = parser.parse_args()


    if args.version:
        print(__version__)
    else:
        logger.info(f"ipcs v{__version__}")
        logger.info("Host: %s, Port: %s" % (args.host, args.port))
        server = Server(args.server_id)

        @server.route()
        async def ping(request: Request):
            return "pong"

        @server.route("print")
        def print_(request, *args, **kwargs):
            print(request, *args, **kwargs)

        server.run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()