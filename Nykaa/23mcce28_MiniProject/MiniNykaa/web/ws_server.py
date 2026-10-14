"""
web/ws_server.py
-----------------
A minimal WebSocket server written directly on raw TCP sockets (RFC 6455),
no third-party library. Browsers cannot open raw TCP sockets, but they CAN
open a WebSocket, so this is how the website gets a persistent, two-way
socket connection to the backend side.

What it does: a background thread polls the Gateway (STATUS + LIST_CATALOG,
over the normal socket protocol) every 2 seconds and PUSHES a JSON message
to every connected browser whenever node health or any product's stock
changes. The page then updates itself instantly with no polling from the
browser and no manual refresh - e.g. someone else buys the last unit and
your product card flips to OUT OF STOCK.

Implemented parts of RFC 6455:
  * HTTP Upgrade handshake: Sec-WebSocket-Accept = base64(sha1(key + GUID))
  * Server -> client text frames (unmasked), with 7/16/64-bit lengths
  * Client -> server frames (masked): ping, close and text are parsed
"""

import base64
import hashlib
import json
import socket
import struct
import threading
import time

from common import config
from common.protocol import request as rpc_request

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"   # fixed constant from RFC 6455


def _log(msg):
    print(f"[ws] {msg}", flush=True)


def encode_frame(text: str, opcode: int = 0x1) -> bytes:
    payload = text.encode("utf-8")
    header = bytearray([0x80 | opcode])                 # FIN + opcode
    n = len(payload)
    if n < 126:
        header.append(n)
    elif n < 65536:
        header.append(126)
        header += struct.pack("!H", n)
    else:
        header.append(127)
        header += struct.pack("!Q", n)
    return bytes(header) + payload


def _recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("closed")
        buf += chunk
    return buf


def read_frame(sock):
    """Return (opcode, payload_bytes) for one client frame (always masked)."""
    b1, b2 = _recv_exact(sock, 2)
    opcode = b1 & 0x0F
    masked = b2 & 0x80
    length = b2 & 0x7F
    if length == 126:
        (length,) = struct.unpack("!H", _recv_exact(sock, 2))
    elif length == 127:
        (length,) = struct.unpack("!Q", _recv_exact(sock, 8))
    mask = _recv_exact(sock, 4) if masked else b"\x00\x00\x00\x00"
    data = bytearray(_recv_exact(sock, length))
    for i in range(length):
        data[i] ^= mask[i % 4]
    return opcode, bytes(data)


class WebSocketHub:
    def __init__(self):
        self.clients = []
        self.lock = threading.Lock()
        self.last_payload = None

    # ---------------------------------------------------------- handshake
    def _handshake(self, conn):
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = conn.recv(4096)
            if not chunk:
                return False
            data += chunk
        headers = {}
        for line in data.decode("latin-1").split("\r\n")[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()
        key = headers.get("sec-websocket-key")
        if not key or headers.get("upgrade", "").lower() != "websocket":
            conn.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n")
            return False
        accept = base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()
        conn.sendall(("HTTP/1.1 101 Switching Protocols\r\n"
                      "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                      f"Sec-WebSocket-Accept: {accept}\r\n\r\n").encode())
        return True

    def _client_loop(self, conn, addr):
        try:
            if not self._handshake(conn):
                return
            with self.lock:
                self.clients.append(conn)
                snapshot = self.last_payload
            _log(f"client connected {addr} ({len(self.clients)} total)")
            if snapshot:
                conn.sendall(encode_frame(snapshot))
            while True:
                opcode, payload = read_frame(conn)
                if opcode == 0x8:            # close
                    break
                if opcode == 0x9:            # ping -> pong
                    conn.sendall(encode_frame(payload.decode("utf-8", "ignore"), 0xA))
        except Exception:
            pass
        finally:
            with self.lock:
                if conn in self.clients:
                    self.clients.remove(conn)
            try:
                conn.close()
            except Exception:
                pass
            _log(f"client left {addr} ({len(self.clients)} total)")

    # ----------------------------------------------------------- broadcast
    def broadcast(self, text):
        frame = encode_frame(text)
        dead = []
        with self.lock:
            targets = list(self.clients)
        for c in targets:
            try:
                c.sendall(frame)
            except Exception:
                dead.append(c)
        if dead:
            with self.lock:
                for c in dead:
                    if c in self.clients:
                        self.clients.remove(c)

    def _poll_loop(self):
        while True:
            try:
                st = rpc_request(config.GATEWAY_HOST, config.GATEWAY_PORT, {"action": "STATUS", "poll": True}, timeout=3)
                cat = rpc_request(config.GATEWAY_HOST, config.GATEWAY_PORT, {"action": "LIST_CATALOG", "poll": True}, timeout=3)
                stock = {p["product_id"]: p["stock"] for p in cat.get("products", [])}
                payload = json.dumps({"type": "update", "nodes": st.get("nodes", {}), "stock": stock},
                                     sort_keys=True)
            except Exception:
                payload = json.dumps({"type": "update", "nodes": {}, "stock": {}, "gateway": "DOWN"})
            if payload != self.last_payload:         # push only on change
                self.last_payload = payload
                self.broadcast(payload)
            time.sleep(2)

    # --------------------------------------------------------------- serve
    def serve_forever(self):
        threading.Thread(target=self._poll_loop, daemon=True).start()
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((config.BIND_HOST, config.WS_PORT))
        srv.listen(50)
        _log(f"WebSocket server on ws://{config.BIND_HOST}:{config.WS_PORT}")
        while True:
            conn, addr = srv.accept()
            threading.Thread(target=self._client_loop, args=(conn, addr), daemon=True).start()


def start_in_background():
    hub = WebSocketHub()
    threading.Thread(target=hub.serve_forever, daemon=True).start()
    return hub
