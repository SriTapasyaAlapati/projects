"""
gateway/gateway_server.py
--------------------------
One GATEWAY instance. Several run side by side behind the load balancer
(gateway-1, gateway-2); they are STATELESS apart from a small cache, so any
of them can answer any request. Clients never talk to a gateway directly -
they talk to the load balancer (gateway/load_balancer.py).

A gateway:
  1. Routes single-product reads to the right catalog shard (consistent
     hashing) and fans list/search out to every healthy shard (scatter-gather).
  2. Keeps an LRU+TTL CACHE of catalog reads (common/lru_cache.py). Anything
     that decides whether money changes hands - stock checks at add-to-cart
     and checkout - always BYPASSES the cache and reads the shard directly.
  3. Invalidates its cache whenever stock changes (checkout, cancel) and tells
     its peer gateways to do the same, so a stale count is never served for
     long even though each gateway has its own cache; the TTL bounds the
     worst case if an invalidation message is lost.
  4. Finds the order-service LEADER (elected by the Bully algorithm among the
     order nodes) and sends order traffic to it. The leader is not decided
     here - it is asked of the order cluster - so two gateways can never
     disagree about it.
  5. Orchestrates multi-step use cases (CHECKOUT, CANCEL_ORDER) across the
     catalog and order services.

Usage:
    python gateway_server.py gateway-1      (also gateway-2)
"""

import sys
import os
import socket
import threading
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from common import config
from common.protocol import send_msg, recv_msg, request as rpc_request
from common.consistent_hash import ConsistentHashRing
from common.lru_cache import LRUCache
from gateway.health_monitor import HealthMonitor


VERBOSE = os.environ.get("VERBOSE", "0") == "1"
LOGGED_ACTIONS = {"ADD_TO_CART", "UPDATE_CART", "REMOVE_FROM_CART", "CHECKOUT", "CANCEL_ORDER"}


class Gateway:
    def __init__(self, name):
        self.name = name
        self.ring = ConsistentHashRing(nodes=list(config.CATALOG_NODES.keys()))

        watched = dict(config.CATALOG_NODES)
        watched.update(config.ORDER_NODES)
        self.monitor = HealthMonitor(watched)

        self.cache = LRUCache(capacity=config.CACHE_CAPACITY, ttl=config.CACHE_TTL_SEC)
        self.leader = None                       # cached order-leader name
        self.lock = threading.Lock()

    def log(self, msg):
        print(f"[{self.name}] {msg}", flush=True)

    # ============================================== order-leader discovery
    def discover_leader(self):
        """Ask the order nodes who is leader; trust only a node that says it
        is the leader itself."""
        for n in sorted(config.ORDER_NODES, key=lambda x: -config.ORDER_NODES[x]["id"]):
            c = config.ORDER_NODES[n]
            try:
                r = rpc_request(c["host"], c["port"], {"action": "WHO_LEADER"}, timeout=1.0)
                if r.get("is_leader"):
                    if self.leader != n:
                        self.log(f"order leader is now {n}")
                    self.leader = n
                    return n
            except Exception:
                continue
        self.leader = None
        return None

    def order_call(self, msg, attempts=8):
        """Send a request to the current order leader, re-discovering it if
        the cached one is gone or no longer leads (an election may be in
        progress, so retry for a few seconds)."""
        for _ in range(attempts):
            leader = self.leader or self.discover_leader()
            if leader:
                c = config.ORDER_NODES[leader]
                try:
                    r = rpc_request(c["host"], c["port"], msg, timeout=3.0)
                    if r.get("status") != "NOT_LEADER":
                        r["served_by"] = leader
                        return r
                except Exception:
                    pass
                self.leader = None
            time.sleep(0.6)
        return {"status": "ERROR",
                "message": "order service has no leader right now (election in progress) - please retry"}

    # ================================================================ cache
    def invalidate_cache(self, broadcast=True):
        self.cache.clear()
        if broadcast:
            for n, c in config.GATEWAY_NODES.items():
                if n == self.name:
                    continue
                threading.Thread(target=self._tell_peer, args=(c,), daemon=True).start()

    @staticmethod
    def _tell_peer(c):
        try:
            rpc_request(c["host"], c["port"], {"action": "CACHE_INVALIDATE"}, timeout=1.0)
        except Exception:
            pass          # peer down: its TTL still bounds staleness

    # ============================================================== catalog
    def up_catalog_nodes(self):
        return [n for n in config.CATALOG_NODES if self.monitor.is_up(n)]

    def _fan_out(self, request):
        merged, used = [], []
        for n in self.up_catalog_nodes():
            c = config.CATALOG_NODES[n]
            try:
                r = rpc_request(c["host"], c["port"], request)
                if r.get("status") == "OK":
                    merged.extend(r["products"])
                    used.append(n)
            except Exception as exc:
                self.log(f"{request['action']} failed against {n}: {exc}")
                self.monitor.mark_down(n)
        return merged, used

    def list_catalog(self, count=True):
        hit, val = self.cache.get(("LIST",), count)
        if hit:
            return val
        val = self._fan_out({"action": "LIST"})
        if val[1]:
            self.cache.set(("LIST",), val)
        return val

    def search_catalog(self, keyword, category, count=True):
        key = ("SEARCH", (keyword or "").lower(), (category or "").lower())
        hit, val = self.cache.get(key, count)
        if hit:
            return val
        val = self._fan_out({"action": "SEARCH", "keyword": keyword, "category": category})
        if val[1]:
            self.cache.set(key, val)
        return val

    def get_product(self, product_id, use_cache=False):
        """Returns (product, shard, reason). Display reads may use the cache;
        stock-decision reads must pass use_cache=False."""
        if use_cache:
            hit, val = self.cache.get(("GET", product_id))
            if hit:
                return val
        node = self.ring.get_node(product_id)
        if not self.monitor.is_up(node):
            return None, node, "SHARD_DOWN"
        c = config.CATALOG_NODES[node]
        try:
            r = rpc_request(c["host"], c["port"], {"action": "GET", "product_id": product_id})
        except Exception as exc:
            self.monitor.mark_down(node)
            return None, node, f"ERROR:{exc}"
        if r.get("status") == "OK":
            val = (r["product"], node, "OK")
            if use_cache:
                self.cache.set(("GET", product_id), val)
            return val
        return None, node, r.get("status", "NOT_FOUND")

    def check_stock_for_qty(self, product_id, total_qty):
        product, _shard, reason = self.get_product(product_id, use_cache=False)   # always fresh
        if product is None:
            return False, f"product {product_id} unavailable ({reason})", None
        if total_qty > product["stock"]:
            if product["stock"] == 0:
                return False, f"{product['name']} is out of stock", product
            return False, (f"only {product['stock']} of {product['name']} left in stock "
                           f"(you asked for {total_qty})"), product
        return True, "OK", product

    # ================================================================ orders
    def checkout(self, user_id):
        cart_reply = self.order_call({"action": "VIEW_CART", "user_id": user_id})
        if cart_reply.get("status") != "OK":
            return cart_reply
        cart = cart_reply.get("cart", {})
        if not cart:
            return {"status": "ERROR", "message": "cart is empty"}

        items, total = [], 0
        for pid, qty in cart.items():
            product, _s, reason = self.get_product(pid, use_cache=False)
            if product is None:
                return {"status": "ERROR", "message": f"product {pid} unavailable ({reason})"}
            if product["stock"] < qty:
                return {"status": "ERROR", "message": f"insufficient stock for {product['name']}"}
            items.append({"product_id": pid, "name": product["name"], "price": product["price"], "qty": qty})
            total += product["price"] * qty

        for item in items:
            node = self.ring.get_node(item["product_id"])
            c = config.CATALOG_NODES[node]
            try:
                r = rpc_request(c["host"], c["port"], {"action": "DECREMENT_STOCK",
                                                       "product_id": item["product_id"], "qty": item["qty"]})
                if r.get("status") != "OK":
                    self.invalidate_cache()
                    return {"status": "ERROR", "message": f"stock update failed for {item['name']}"}
            except Exception as exc:
                return {"status": "ERROR", "message": f"catalog shard error: {exc}"}
        self.invalidate_cache()                      # stock changed
        return self.order_call({"action": "PLACE_ORDER", "user_id": user_id,
                                "items": items, "total_amount": total})

    def cancel_order(self, user_id, order_id):
        reply = self.order_call({"action": "CANCEL_ORDER", "user_id": user_id, "order_id": order_id})
        if reply.get("status") != "OK":
            return reply
        restocked, failed = [], []
        for item in reply["order"]["items"]:
            node = self.ring.get_node(item["product_id"])
            c = config.CATALOG_NODES[node]
            try:
                r = rpc_request(c["host"], c["port"], {"action": "INCREMENT_STOCK",
                                                       "product_id": item["product_id"], "qty": item["qty"]})
                (restocked if r.get("status") == "OK" else failed).append(item["product_id"])
            except Exception as exc:
                self.log(f"restock of {item['product_id']} failed: {exc}")
                failed.append(item["product_id"])
        self.invalidate_cache()
        reply["restocked"], reply["restock_failed"] = restocked, failed
        return reply

    def enriched_cart(self, user_id):
        reply = self.order_call({"action": "VIEW_CART", "user_id": user_id})
        if reply.get("status") != "OK":
            return reply
        items = []
        for pid, qty in reply.get("cart", {}).items():
            product, _s, _r = self.get_product(pid, use_cache=False)
            if product is None:
                items.append({"product_id": pid, "name": "(unavailable)", "price": 0, "qty": qty,
                              "stock": 0, "subtotal": 0, "in_stock": False})
            else:
                items.append({"product_id": pid, "name": product["name"], "price": product["price"],
                              "qty": qty, "stock": product["stock"], "subtotal": product["price"] * qty,
                              "in_stock": qty <= product["stock"]})
        reply["items"] = items
        reply["total"] = sum(i["subtotal"] for i in items)
        return reply

    # ============================================================== dispatch
    def handle(self, req):
        a = req.get("action")

        if a == "PING":
            return {"status": "OK", "node": self.name, "role": "gateway"}
        if a == "GATEWAY_INFO":
            return {"status": "OK", "gateway": self.name, "cache": self.cache.stats()}
        if a == "CACHE_INVALIDATE":
            self.invalidate_cache(broadcast=False)
            self.log("cache invalidated by a peer gateway")
            return {"status": "OK"}
        if a == "STATUS":
            snap = self.monitor.snapshot()
            snap["active_order_node"] = self.discover_leader()   # always verify: the cached value may be stale
            return {"status": "OK", "nodes": snap, "gateway": self.name, "cache": self.cache.stats()}

        if a == "LIST_CATALOG":
            products, shards = self.list_catalog(count=not req.get("poll"))
            return {"status": "OK", "products": products, "shards_used": shards, "gateway": self.name}
        if a == "SEARCH_CATALOG":
            products, shards = self.search_catalog(req.get("keyword"), req.get("category"))
            return {"status": "OK", "products": products, "shards_used": shards, "gateway": self.name}
        if a == "GET_PRODUCT":
            product, shard, reason = self.get_product(req["product_id"], use_cache=True)
            if product:
                return {"status": "OK", "product": product, "shard": shard}
            return {"status": "ERROR", "message": reason, "shard": shard}

        if a == "ADD_TO_CART":
            pid, qty = req["product_id"], int(req.get("qty", 1))
            have = self.order_call({"action": "VIEW_CART", "user_id": req["user_id"]})
            if have.get("status") != "OK":
                return have
            ok, message, product = self.check_stock_for_qty(pid, have["cart"].get(pid, 0) + qty)
            if not ok:
                return {"status": "OUT_OF_STOCK", "message": message,
                        "available_stock": product["stock"] if product else 0}
            return self.order_call(req)
        if a == "UPDATE_CART":
            qty = int(req.get("qty", 0))
            if qty > 0:
                ok, message, product = self.check_stock_for_qty(req["product_id"], qty)
                if not ok:
                    return {"status": "OUT_OF_STOCK", "message": message,
                            "available_stock": product["stock"] if product else 0}
            return self.order_call({"action": "UPDATE_CART", "user_id": req["user_id"],
                                    "product_id": req["product_id"], "qty": max(qty, 0)})
        if a == "REMOVE_FROM_CART":
            return self.order_call(req)
        if a == "VIEW_CART":
            return self.enriched_cart(req["user_id"])
        if a == "VIEW_ORDERS":
            return self.order_call(req)
        if a == "CHECKOUT":
            return self.checkout(req["user_id"])
        if a == "CANCEL_ORDER":
            return self.cancel_order(req["user_id"], req["order_id"])
        return {"status": "ERROR", "message": f"unknown action {a}"}

    def handle_client(self, conn, addr):
        try:
            req = recv_msg(conn)
            # Routine read-only traffic (and the website's background polling)
            # would flood the console, so by default only state-changing
            # actions are logged. Set VERBOSE=1 to log everything.
            if VERBOSE or (req.get("action") in LOGGED_ACTIONS and not req.get("poll")):
                self.log(f"{req.get('action')} {req.get('user_id', '')}".strip())
            send_msg(conn, self.handle(req))
        except Exception as exc:
            self.log(f"error handling {addr}: {exc}")
            try:
                send_msg(conn, {"status": "ERROR", "message": str(exc)})
            except Exception:
                pass
        finally:
            conn.close()

    def serve_forever(self):
        self.monitor.start()
        me = config.GATEWAY_NODES[self.name]
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((config.BIND_HOST, me["port"]))
        srv.listen(100)
        self.log(f"gateway listening on {config.BIND_HOST}:{me['port']} "
                 f"(cache: LRU capacity={config.CACHE_CAPACITY}, TTL={config.CACHE_TTL_SEC}s)")
        while True:
            conn, addr = srv.accept()
            threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True).start()


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "gateway-1"
    if name not in config.GATEWAY_NODES:
        print(f"Usage: python gateway_server.py <{'|'.join(config.GATEWAY_NODES)}>")
        sys.exit(1)
    try:
        Gateway(name).serve_forever()
    except KeyboardInterrupt:
        print(f"\n[{name}] shutting down.")
