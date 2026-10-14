"""Unit tests for the length-prefixed JSON wire protocol (common/protocol.py)."""
import socket
import struct
import threading

import pytest
from common.protocol import send_msg, recv_msg


def pair():
    return socket.socketpair()


def test_round_trip():
    a, b = pair()
    send_msg(a, {"action": "PING", "n": [1, 2, 3], "text": "héllo ₹"})
    assert recv_msg(b) == {"action": "PING", "n": [1, 2, 3], "text": "héllo ₹"}


def test_two_messages_sent_back_to_back_stay_separate():
    """TCP is a byte stream: the framing must keep message boundaries."""
    a, b = pair()
    send_msg(a, {"i": 1}); send_msg(a, {"i": 2})
    assert recv_msg(b) == {"i": 1} and recv_msg(b) == {"i": 2}


def test_large_message():
    a, b = pair()
    big = {"blob": "x" * 500_000}
    t = threading.Thread(target=send_msg, args=(a, big)); t.start()
    assert recv_msg(b) == big
    t.join()


def test_message_split_across_many_tiny_writes():
    import json
    a, b = pair()
    payload = json.dumps({"k": "v" * 50}).encode()
    data = struct.pack("!I", len(payload)) + payload

    def dribble():
        for i in range(0, len(data), 3):
            a.sendall(data[i:i + 3])
    t = threading.Thread(target=dribble); t.start()
    assert recv_msg(b) == {"k": "v" * 50}
    t.join()


def test_closed_connection_mid_frame_raises():
    a, b = pair()
    a.sendall(struct.pack("!I", 100) + b"short")      # promises 100 bytes, sends 5
    a.close()
    with pytest.raises(ConnectionError):
        recv_msg(b)
