
from sys import argv

import logging

from ipcs.client import logger
from ipcs import Client

client = Client(argv[1])

logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("[%(name)s] [%(levelname)s] %(message)s"))
logger.addHandler(handler)

@client.route()
async def hello(request):
    # print("Hello, World!")
    ...

@client.route()
async def test(request):
    print("test")

@client.route("rs")
async def request_to_server(request, command):
    print(await client.connections.__IPCS_SERVER__.request(command))

@client.route()
async def error(request):
    print(request)
    raise ValueError("test")

@client.listen()
async def on_connect(id_):
    if id_ == client.id_:
        return
    if len(argv) < 3:
        from time import time
        result = []
        print(await client.connections[id_].request("test"))
        for _ in range(1000):
            start = time()
            await client.connections[id_].request("hello")
            result.append(time() - start)
        print(sum(result) / len(result))
    else:
        await eval(argv[2])

client.run("ws://localhost/", port=8080)