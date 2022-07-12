
from sys import argv

from ipcs import Client

client = Client(argv[1])

@client.route()
async def hello(request, a):
    # print("Hello, World!")
    ...

@client.route()
async def test(request):
    print("test")

@client.listen()
async def on_connect(id_):
    if id_ == client.id_:
        return
    from time import time
    result = []
    print(await client.connections[id_].request("test"))
    for _ in range(1000):
        start = time()
        await client.connections[id_].request("hello")
        result.append(time() - start)
    print(sum(result) / len(result))

client.run("ws://localhost/", port=8080)