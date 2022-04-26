# ipcs Examples - Chat Client

from aioconsole import ainput
from ipcs import IpcsClient


client = IpcsClient(input("UserName:"))
print("Connecting...")


@client.listen()
async def on_connect_at_server(id_):
    print("SERVER: Joined", id_)


@client.listen()
async def on_disconnect_at_server(id_):
    print("SERVER: Leaved", id_)


@client.route()
async def recv(id_, message):
    print(f"{id_}: {message}")


def client_print(content):
    print("CLIENT:\t%s" % content.replace("\n", "\n\t"))


@client.listen()
async def on_ready():
    print("Ipcs Example - Chat\n")
    print("# How to\nhelp\tDisplays help\nusers\tDisplays users (ids)\nsend\tSend message\n")
    while client.connected.is_set():
        content: str = await ainput()
        if content.startswith("send "):
            for target in filter(lambda x: x != client.id_, client.clients):
                if target != "__IPCS_SERVER__":
                    await client.request(
                        target, "recv", client.id_,
                        content[5:]
                    )
                    print(f"{client.id_} (you): {content}")
        elif content == "users":
            client_print("Users:\n%s" % "\n".join(f"{id_}" for id_ in client.clients))
        else:
            client_print("It is wrong way to use this.")


client.run(uri="ws://localhost/", port=8080)