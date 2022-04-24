# Quick Start
## Installation
You can install ipcs using pip.  
`pip install ipcs`

## Example
### Route
A Route is a function that can be called by the connection partner.  
You can register a Route with `IpcsClient.route`.  
This time, we will create a Route that executes `print`.
```python
from ipcs import IpcsClient

client = IpcsClient()

@client.route()
async def display(message):
    print(message)

client.run()
```
### Request
The request is for calling the other client's Route.  
Requests can be made from `IpcsClient.request`.  
The first argument is the ID of the client to which the message is sent.  
```python
await client.request(id_, "display", "Hello, World!")
```
### Event
An event is a function that is called at a specific time.  
For example, an event `on_connect_at_server` is called when another client connects.  
Events can be made to be called by adding a `IpcsClient.listen` decorator to the function.  
In this example, we create a program that, when another client connects, calls the `display` route of that client to display `Hello, World!`.
```python
from ipcs import IpcsClient

client = IpcsClient()

@client.route()
async def display(message):
    print(message)

@client.listen()
async def on_connect_at_server(id_):
    # If another client connect to server.
    await client.request(id_, "display", "Hello, World!")

client.run(uri="ws://localhost/", port=8080)
```
### Server
Servers that relay communications between clients do not need to be programmed.  
You can run a relay server with `ipcs-server`.
#### Notes
Of course, it is possible to create a program to customize it.  
In that case, use `IpcsServer`.  
You can probably embed it in your web server.
### Run
Try running two of the above codes after you run the server.  
When you start the second one, you should see `Hello, World!` on the console of the second one.

## Console
Run `ipc-server --help` to see help information.