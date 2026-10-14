"""
web/web_server.py
-------------------
A small HTTP server that turns MiniNykaa into a real website.

Important: this does NOT contain any shopping logic. It is a thin bridge
that (a) serves the static HTML/CSS/JS in web/static, and (b) translates
each REST call into the exact same length-prefixed JSON/TCP-socket request
that the CLI and Tkinter clients send to the Gateway (see
common/protocol.py). All catalog sharding, cart/order handling, stock
validation, replication and failover still happen in the socket-based
microservices behind the Gateway - the website only changes how a human
reaches them.

Built with Python's standard-library http.server (itself built on top of
`socketserver`/`socket`), so no third-party web framework is used.

Usage:
    python web/web_server.py
Then open http://localhost:8080 in a browser.
"""

import sys
import os
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from common import config
from common.protocol import request as rpc_request
from web import ws_server

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

MIME = {".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "application/javascript",
        ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon", ".json": "application/json"}


VERBOSE = os.environ.get("VERBOSE", "0") == "1"
# Host shown in the READY banner. 0.0.0.0 is a bind address, not something
# you can type into a browser, so we print "localhost" (override with PUBLIC_HOST).
PUBLIC_HOST = os.environ.get("PUBLIC_HOST", "localhost")


def system_ready():
    """True when the load balancer answers, every gateway is UP, all catalog
    shards are UP and the order cluster has an elected leader."""
    st = gateway("STATUS")
    if st.get("status") != "OK":
        return False, "load balancer not reachable yet"
    nodes, gws = st.get("nodes", {}), st.get("gateways", {})
    down = [n for n, i in gws.items() if i.get("state") != "UP"]
    down += [n for n, v in nodes.items() if n != "active_order_node" and v != "UP"]
    if down:
        return False, "waiting for: " + ", ".join(sorted(down))
    if not nodes.get("active_order_node"):
        return False, "waiting for the order cluster to elect a leader"
    return True, st


def announce_when_ready():
    """Background thread: print a clear READY banner once the whole system is up."""
    last_msg, started = None, time.time()
    while True:
        ok, info = system_ready()
        if ok:
            leader = info["nodes"]["active_order_node"]
            bar = "=" * 62
            print(f"\n{bar}\n  MiniNykaa is READY\n"
                  f"    Website (open in your browser) : http://{PUBLIC_HOST}:{config.WEB_PORT}\n"
                  f"    Live-update WebSocket          : ws://{PUBLIC_HOST}:{config.WEB_PORT + 1}\n"
                  f"    Load balancer (front door)     : {PUBLIC_HOST}:{config.GATEWAY_PORT}   [{info['lb']['algo']}]\n"
                  f"    Gateways: {', '.join(info['gateways'])}   Order leader: {leader}\n"
                  f"{bar}\n", flush=True)
            return
        if info != last_msg:
            print(f"[web] starting up... {info}", flush=True)
            last_msg = info
        if time.time() - started > 90:
            print("[web] still not fully ready after 90 s - the site is up but some nodes are not. "
                  "Check the other containers' logs.", flush=True)
            return
        time.sleep(1.5)


def gateway(action, **kwargs):
    msg = {"action": action}
    msg.update(kwargs)
    try:
        return rpc_request(config.GATEWAY_HOST, config.GATEWAY_PORT, msg, timeout=5.0)
    except Exception as exc:
        return {"status": "ERROR", "message": f"gateway unreachable: {exc}"}


class Handler(BaseHTTPRequestHandler):
    server_version = "MiniNykaaWeb/1.0"

    def log_message(self, fmt, *args):
        # Quiet by default: the page makes many GET requests, which would
        # bury the READY banner. Only state-changing POSTs are logged
        # (VERBOSE=1 logs everything).
        if VERBOSE or self.command == "POST":
            print(f"[web] {self.address_string()} - {fmt % args}", flush=True)

    # ---------------------------------------------------------------- utils
    def _send_json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path):
        if not os.path.isfile(path):
            self.send_error(404, "Not found")
            return
        ext = os.path.splitext(path)[1]
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _user_id(self, query=None):
        """The site has no real authentication (out of scope - see SRS).
        The browser picks a user id at 'sign in' and sends it on every API
        call either as ?user=... or in a JSON body's "user_id" field."""
        if query and query.get("user"):
            return query["user"][0]
        return "guest"

    def _body_json(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    # ------------------------------------------------------------- routing
    def do_GET(self):
        parsed = urlparse(self.path)
        path, query = parsed.path, parse_qs(parsed.query)

        if path == "/" or path == "":
            return self._send_file(os.path.join(STATIC_DIR, "index.html"))

        if path == "/api/catalog":
            keyword = query.get("q", [None])[0]
            category = query.get("category", [None])[0]
            if keyword or category:
                reply = gateway("SEARCH_CATALOG", keyword=keyword, category=category)
            else:
                reply = gateway("LIST_CATALOG")
            return self._send_json(reply)

        if path.startswith("/api/product/"):
            pid = path.rsplit("/", 1)[-1]
            return self._send_json(gateway("GET_PRODUCT", product_id=pid))

        if path == "/api/cart":
            return self._send_json(gateway("VIEW_CART", user_id=self._user_id(query)))

        if path == "/api/orders":
            return self._send_json(gateway("VIEW_ORDERS", user_id=self._user_id(query)))

        if path == "/api/status":
            return self._send_json(gateway("STATUS"))

        # static files (css/js/images)
        safe_rel = os.path.normpath(path).lstrip(os.sep)
        file_path = os.path.join(STATIC_DIR, safe_rel)
        if os.path.commonpath([os.path.abspath(file_path), os.path.abspath(STATIC_DIR)]) != os.path.abspath(STATIC_DIR):
            self.send_error(403)
            return
        return self._send_file(file_path)

    def do_POST(self):
        parsed = urlparse(self.path)
        path, query = parsed.path, parse_qs(parsed.query)
        body = self._body_json()
        user_id = body.get("user_id") or self._user_id(query)

        if path == "/api/cart/add":
            reply = gateway("ADD_TO_CART", user_id=user_id,
                            product_id=body.get("product_id"), qty=int(body.get("qty", 1)))
            return self._send_json(reply)

        if path == "/api/cart/update":
            reply = gateway("UPDATE_CART", user_id=user_id,
                            product_id=body.get("product_id"), qty=int(body.get("qty", 0)))
            return self._send_json(reply)

        if path == "/api/cart/remove":
            reply = gateway("REMOVE_FROM_CART", user_id=user_id, product_id=body.get("product_id"))
            return self._send_json(reply)

        if path == "/api/orders/cancel":
            reply = gateway("CANCEL_ORDER", user_id=user_id, order_id=body.get("order_id"))
            return self._send_json(reply)

        if path == "/api/checkout":
            reply = gateway("CHECKOUT", user_id=user_id)
            return self._send_json(reply)

        self.send_error(404, "Unknown API route")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def main():
    ws_server.start_in_background()
    addr = (config.BIND_HOST, config.WEB_PORT)
    httpd = ThreadingHTTPServer(addr, Handler)
    print(f"[web] web server listening on {config.BIND_HOST}:{config.WEB_PORT} "
          f"(front door = {config.GATEWAY_HOST}:{config.GATEWAY_PORT}); checking the rest of the system...", flush=True)
    threading.Thread(target=announce_when_ready, daemon=True).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[web] shutting down.")


if __name__ == "__main__":
    main()
