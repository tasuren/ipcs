[![PyPI](https://img.shields.io/pypi/v/ipcs)](https://pypi.org/project/ipcs/) ![PyPI - Python Version](https://img.shields.io/pypi/pyversions/ipcs) ![PyPI - Downloads](https://img.shields.io/pypi/dm/ipcs) ![PyPI - License](https://img.shields.io/pypi/l/ipcs) [![Documentation Status](https://readthedocs.org/projects/ipcs/badge/?version=latest)](https://ipcs.readthedocs.io/en/latest/?badge=latest) [![Discord](https://img.shields.io/discord/777430548951728149?label=chat&logo=discord)](https://discord.gg/kfMwZUyGFG) [![Buy Me a Coffee](https://img.shields.io/badge/-tasuren-E9EEF3?label=Buy%20Me%20a%20Coffee&logo=buymeacoffee)](https://www.buymeacoffee.com/tasuren)
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