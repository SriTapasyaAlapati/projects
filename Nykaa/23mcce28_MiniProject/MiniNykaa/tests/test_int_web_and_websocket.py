"""Integration tests: the website's HTTP bridge and the hand-written WebSocket server."""
import base64
import http.client
import json
import os
import socket
import struct
import time
import urllib.request

from tests.conftest import call, wait_until
from common import config


def http_json(url, body=None):
    req = urllib.request.Request(url, json.dumps(body).encode() if body is not None else None,
                                 {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=15))


def test_home_page_and_static_assets(stack, web_url):
    html = urllib.request.urlopen(web_url + "/").read().decode()
    assert "nykaa-logo.png" in html and "app.js" in html
    logo = urllib.request.urlopen(web_url + "/img/nykaa-logo.png")
    assert logo.headers["Content-Type"] == "image/png"
    svg = urllib.request.urlopen(web_url + "/img/P004.svg")
    assert svg.headers["Content-Type"] == "image/svg+xml"


def test_every_product_has_an_image(stack, web_url):
    for p in http_json(web_url + "/api/catalog")["products"]:
        assert urllib.request.urlopen(f"{web_url}/img/{p['product_id']}.svg").status == 200


def test_cannot_read_files_outside_the_static_folder(stack):
    c = http.client.HTTPConnection("127.0.0.1", config.WEB_PORT, timeout=5)
    c.request("GET", "/../common/config.py")
    r = c.getresponse()
    assert r.status in (403, 404) and b"BIND_HOST" not in r.read()


def test_catalog_and_status_api(stack, web_url):
    cat = http_json(web_url + "/api/catalog")
    assert cat["status"] == "OK" and len(cat["products"]) == 20
    st = http_json(web_url + "/api/status")
    assert st["lb"]["algo"] == "round_robin" and st["nodes"]["active_order_node"] == "order-3"


def test_full_shopping_flow_through_the_website_api(stack, web_url, user):
    assert http_json(web_url + "/api/cart/add", {"user_id": user, "product_id": "P012", "qty": 2})["status"] == "OK"
    assert http_json(web_url + "/api/cart/update", {"user_id": user, "product_id": "P012", "qty": 1})["cart"] == {"P012": 1}
    over = http_json(web_url + "/api/cart/update", {"user_id": user, "product_id": "P012", "qty": 99999})
    assert over["status"] == "OUT_OF_STOCK"
    oid = http_json(web_url + "/api/checkout", {"user_id": user})["order"]["order_id"]
    assert http_json(web_url + "/api/orders/cancel", {"user_id": user, "order_id": oid})["status"] == "OK"
    orders = http_json(f"{web_url}/api/orders?user={user}")["orders"]
    assert orders[0]["status"] == "CANCELLED"


# ----------------------------------------------------------------- WebSocket
class WS:
    """Tiny RFC 6455 client on a raw socket."""
    def __init__(self):
        self.s = socket.create_connection(("127.0.0.1", config.WS_PORT), timeout=10)
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall((f"GET / HTTP/1.1\r\nHost: x\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                        f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        self.buf = b""
        while b"\r\n\r\n" not in self.buf:
            self.buf += self.s.recv(4096)
        head, self.buf = self.buf.split(b"\r\n\r\n", 1)
        self.head = head.decode()
        self.key = key

    def _need(self, n):
        while len(self.buf) < n:
            chunk = self.s.recv(4096)
            if not chunk:
                raise ConnectionError("closed")
            self.buf += chunk

    def recv_json(self, timeout=10):
        self.s.settimeout(timeout)
        self._need(2)
        n, off = self.buf[1] & 0x7F, 2
        if n == 126:
            self._need(4); n, off = struct.unpack("!H", self.buf[2:4])[0], 4
        self._need(off + n)
        data, self.buf = self.buf[off:off + n], self.buf[off + n:]
        return json.loads(data)


def test_websocket_handshake_follows_rfc6455(stack):
    import hashlib
    ws = WS()
    expected = base64.b64encode(hashlib.sha1((ws.key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
    assert ws.head.startswith("HTTP/1.1 101")
    assert f"Sec-WebSocket-Accept: {expected}" in ws.head


def test_websocket_pushes_a_stock_change_without_polling(stack, user):
    ws = WS()
    first = ws.recv_json()
    assert first["type"] == "update" and "P013" in first["stock"]
    start = first["stock"]["P013"]
    call("ADD_TO_CART", user_id=user, product_id="P013", qty=2)
    call("CHECKOUT", user_id=user)
    deadline, seen = time.time() + 10, None
    while time.time() < deadline:
        msg = ws.recv_json(timeout=10)
        if msg["stock"].get("P013") == start - 2:
            seen = msg
            break
    assert seen is not None, "no push arrived with the reduced stock"


def test_non_websocket_request_is_rejected(stack):
    s = socket.create_connection(("127.0.0.1", config.WS_PORT), timeout=5)
    s.sendall(b"GET / HTTP/1.1\r\nHost: x\r\n\r\n")
    assert s.recv(100).startswith(b"HTTP/1.1 400")
