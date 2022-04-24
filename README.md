# ipcs
A library for Python for IPC.  

**WARNING** This library is currently in alpha.

## Installation
`pip install ipcs`

## Examples
Run `ipcs-server` and run following code.
### Client A
```python
# Client A

from ipcs import IpcsClient

client = IpcsClient("A")

@client.route()
async def hello():
    print("Hello, World!")

client.run(uri="ws://localhost/", port=8080)
```
### Client B
```python
# Client B

from ipcs import IpcsClient

client = IpcsClient("B")

@client.listen()
async def on_ready():
    await client.request("A", "hello")

client.run(uri="ws://localhost/", port=8080)
```

## LICENSE
MIT License

## Contributing
Do not break the style of the code.  
Issues and PullRequests should be brief in content.

## Documentation
Documentation is avaliable [here](https://ipcs.readthedocs.io/en/latest/).