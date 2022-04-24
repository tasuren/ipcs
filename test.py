
from ipcs import IpcsClient

client = IpcsClient()

@client.route()
async def display(message):
    print(message)

@client.listen()
async def on_connect_at_server(uuid):
    await client.request("display", "Hello, World!", target=uuid)

client.run(uri="ws://localhost/", port=8080)