# ipcs Examples - Chat Client

from aioconsole import ainput
from ipcs import IpcsClient


client = IpcsClient()


@client.listen()
async def on_connect_at_server(uuid):
    print("SERVER: Joined", uuid)


@client.listen()
async def on_disconnect_at_server(uuid):
    print("SERVER: Leaved", uuid)


@client.route()
async def recv(uuid, message):
    print(f"{uuid}: {message}")


def client_print(content):
    print("CLIENT:\t%s" % content.replace("\n", "\n\t"))


@client.listen()
async def on_ready():
    print("Ipcs Example - Chat\n")
    print("# How to\nhelp\tDisplays help\nuuids\tDisplays users (uuids)\nsend\tSend message\n\te.g `send 1 Hi` to send message to the 1th UUID\n\tIf set to 0, it will be sent to all.")
    while client.connected.is_set():
        content: str = await ainput("")
        if content.startswith("send "):
            try:
                tentative = content.split()
                uuid_number = tentative[1]
                del tentative
            except IndexError:
                client_print("Argument is missing.")
                continue
            try:
                await client.request(
                    "recv", client.uuid, content := content.replace(f"send {uuid_number} ", ""),
                    target="ALL" if uuid_number == "0" else client.uuids[int(uuid_number) - 1]
                )
            except IndexError:
                client_print("That UUID could not be found.")
            else:
                print(f"{client.uuid}(you): {content}")
        elif content == "uuids":
            client_print("\n".join(f"{i} {uuid}" for i, uuid in enumerate(client.uuids, 1)))
        else:
            client_print("It is wrong way to use this.")


client.run(uri="ws://localhost/", port=8080)