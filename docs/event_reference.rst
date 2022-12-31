.. _event_reference:

Event Reference
===============
These events are called from inside by default.

* ``on_ready()``
    It is called when the client is ready.
* ``on_connect(id_: str)``
    It is called when a new other client connects to the server.
* ``on_disconnect(id_: str)``
    It is called when the other client disconnects from the server.
* ``on_disconnect_from_server()``
    It is called when the client disconnects from the server.
* ``on_close(code: int, reason: str)``
    It is called when the client processes an exit.