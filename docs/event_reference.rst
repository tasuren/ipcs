.. _event_reference:

Event Reference
===============
These events are called from inside by default.

Client Side
-----------
* ``on_ready()``
    It is called when the client is ready.
* ``on_request(sent: RequestPayload)``
    It is called when making a request.
* ``on_response(data: ResponsePayload)``
    It is called when a response is received.
* ``on_send(data: RequestPayload | ResponsePayload)``
    It is called when sending data.
* ``on_receive(data: RequestPayload | ResponsePayload)``
    It is called when receiving data.
* ``on_connect()``
    It is called when the client connects to the server.
* ``on_disconnect()``
    Called when the client disconnects from the server.
* ``on_connect_at_server(id_: Identifier)``
    It is called when a new other client connects to the server.
* ``on_disconnect_at_server(id_: Identifier)``
    It is called when the other client disconnects from the server.
* ``on_close()``
    It is called when the client processes an exit.


Server Side
-----------
* ``on_ready()``
    It is called when the client is ready.
* ``on_send(data: RequestPayload | ResponsePayload)``
    It is called when sending data.
* ``on_receive(data: RequestPayload | ResponsePayload)``
    It is called when receiving data.
* ``on_connect()``
    It is called when the client connects to the server.
* ``on_disconnect()``
    Called when the client disconnects from the server.
* ``on_close()``
    It is called when the client processes an exit.
