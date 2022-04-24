
from ipcs import IpcsClient

client = IpcsClient()

@client.route()
async def hello():
    # print("Hello, World!")
    ...

@client.listen()
async def on_connect_at_server(id_):
    from time import time
    result = []
    for _ in range(50):
        start = time()
        await client.request(id_, "hello")
        result.append(time() - start)
    print(sum(result) / len(result))

client.run(uri="ws://localhost/", port=8080)