# ipcs Examples - Chat Client

from aioconsole import ainput
from ipcs import Client


client = Client(input("UserName:"))
print("Connecting...")


@client.listen()
async def on_connect(id_):
    print("SERVER: Joined", id_)


@client.listen()
async def on_disconnect(id_):
    print("SERVER: Leaved", id_)


@client.route()
async def recv(_, id_, message):
    print(f"{id_}: {message}")


def client_print(content):
    print("CLIENT:\t%s" % content.replace("\n", "\n\t"))


@client.listen()
async def on_ready():
    print("Ipcs Example - Chat\n")
    print("# How to\nusers\tDisplays users (ids)\nsend\tSend message\n")
    while client.ready.is_set():
        content: str = await ainput()
        if content.startswith("send "):
            for target in filter(lambda x: x != client.id_, client.connections):
                if target != "__IPCS_SERVER__":
                    await client.connections[target].request(
                        "recv", client.id_, content[5:]
                    )
                    print(f"{client.id_} (you): {content}")
        elif content == "users":
            client_print("Users:\n%s" % "\n".join(
                f"{id_}" for id_ in client.connections
                if id_ != "__IPCS_SERVER__"
            ))
        else:
            client_print("It is wrong way to use this.")

@client.listen()
async def on_disconnect_from_server():
    client_print("Disconnected from server. Connecting...")


print("Connecting to server...")
client.run(uri="ws://localhost/", port=8080)