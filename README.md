[![PyPI](https://img.shields.io/pypi/v/ipcs)](https://pypi.org/project/ipcs/) ![PyPI - Python Version](https://img.shields.io/pypi/pyversions/ipcs) ![PyPI - Downloads](https://img.shields.io/pypi/dm/ipcs) ![PyPI - License](https://img.shields.io/pypi/l/ipcs) [![Documentation Status](https://readthedocs.org/projects/ipcs/badge/?version=latest)](https://ipcs.readthedocs.io/en/latest/?badge=latest) [![Buy Me a Coffee](https://img.shields.io/badge/-tasuren-E9EEF3?label=Buy%20Me%20a%20Coffee&logo=buymeacoffee)](https://www.buymeacoffee.com/tasuren)
# ipcs
A library for Python for IPC.  
(Although it is written as IPC, it can also be used for communication with an external server.)

## Installation
`$ pip install ipcs`

## Examples
Run `ipcs-server` and run following code.
### Client A
```python
# Client A

from ipcs import Client, Request

client = Client("a")

@client.route()
async def hello(request: Request, word: str):
    print("Hello, %s!" % word)

client.run("ws://localhost/", port=8080)
```
### Client B
```python
# Client B

from ipcs import Client

client = Client("b")

@client.listen()
async def on_ready():
    # Run client a's hello str to say greetings to world.
    await client.request("a", "hello", "World")
    # or `await client.connections.a.request("hello", "World")`

client.run("ws://localhost/", port=8080)
```

## License
The license is MIT and details can be found [here](https://github.com/tasuren/ipcs/blob/main/LICENSE).

## Documentation
Documentation is avaliable [here](https://ipcs.readthedocs.io/en/latest/).
