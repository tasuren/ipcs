# ipcs - setup

from setuptools import setup
from os.path import exists


NAME = "ipcs"
DESCRIPTION = "Simple IPC server/client"


if exists("README.md"):
    with open("README.md", "r") as f:
        long_description = f.read()
else:
    long_description = DESCRIPTION


with open(f"{NAME}/__init__.py", "r") as f:
    text = f.read()
    version = text.split('__version__ = "')[1].split('"')[0]
    author = text.split('__author__ = "')[1].split('"')[0]


setup(
    name=NAME,
    version=version,
    description=DESCRIPTION,
    long_description=long_description,
    long_description_content_type="text/markdown",
    url=f'https://github.com/tasuren/{NAME}',
    project_urls={
        "Documentation": f"https://{NAME}.readthedocs.io/"
    },
    author=author,
    author_email='tasuren@aol.com',
    license='MIT',
    keywords='ipc',
    packages=("ipcs", "ipcs.ext"),
    package_data={"ipcs": ("py.typed",)},
    install_requires=("websockets", "orjson"),
    extras_requires={},
    python_requires='>=3.10.0',
    entry_points={
        "console_scripts": [
            "ipcs-server = ipcs.__main__:main"
        ]
    },
    classifiers=[
        'Programming Language :: Python :: 3.10',
        'Typing :: Typed'
    ]
)