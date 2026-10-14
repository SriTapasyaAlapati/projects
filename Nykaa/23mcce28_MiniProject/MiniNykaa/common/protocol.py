"""
common/protocol.py
-------------------
Shared wire protocol used by every node in MiniNykaa (gateway, catalog
shards, order primary/backup, and the client).

Design notes
~~~~~~~~~~~~
Raw TCP is a byte stream, not a message stream - two independent writes can
arrive as one read(), or one write can be split across several read()s. To
turn it back into discrete JSON messages we use a simple **length-prefixed
framing**: every message is sent as

    [4-byte big-endian length][UTF-8 JSON payload of that many bytes]

recv_msg() keeps reading until it has the full payload, so callers never
have to worry about partial reads. This is the same idea production RPC
systems (gRPC, Thrift, etc.) use under the hood.
"""

import json
import socket
import struct

HEADER_SIZE = 4  # bytes used to encode the payload length


def send_msg(sock: socket.socket, obj: dict) -> None:
    """Serialize `obj` to JSON and send it as one length-prefixed frame."""
    payload = json.dumps(obj).encode("utf-8")
    header = struct.pack("!I", len(payload))
    sock.sendall(header + payload)


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    """Read exactly n bytes from sock, or raise ConnectionError if the peer
    closes early. Loops because a single recv() is not guaranteed to return
    all requested bytes."""
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("socket closed while reading a frame")
        buf += chunk
    return buf


def recv_msg(sock: socket.socket) -> dict:
    """Block until one complete length-prefixed JSON frame has arrived and
    return it as a Python dict."""
    header = _recv_exact(sock, HEADER_SIZE)
    (length,) = struct.unpack("!I", header)
    payload = _recv_exact(sock, length)
    return json.loads(payload.decode("utf-8"))


def request(host: str, port: int, message: dict, timeout: float = 3.0) -> dict:
    """Convenience helper: open a short-lived connection, send one message,
    read one reply, close. Used for health checks and simple service-to-
    service calls where we don't want to hold a persistent connection."""
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        send_msg(sock, message)
        return recv_msg(sock)
