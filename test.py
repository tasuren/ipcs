
from ipcs import IpcsClient

client = IpcsClient()

@client.route()
async def hello():
    # print("Hello, World!")
    ...

@client.route()
async def test():
    print("test")

@client.listen()
async def on_connect_at_server(id_):
    if id_ == client.id_:
        return
    from time import time
    result = []
    print(await client.request("__IPCS_SERVER__", "ping"))
    for _ in range(1000):
        start = time()
        await client.request(id_, "hello")
        result.append(time() - start)
    print(sum(result) / len(result))

client.run(uri="ws://localhost/", port=8080)