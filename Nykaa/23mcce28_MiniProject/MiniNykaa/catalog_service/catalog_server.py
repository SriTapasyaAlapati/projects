"""
catalog_service/catalog_server.py
----------------------------------
A single Catalog microservice instance ("shard"). Run several of these
(one per entry in common.config.CATALOG_NODES) and each one will, at
startup, use the SAME consistent-hash ring to figure out which subset of
products it personally owns. It only ever answers questions about its own
partition - the Gateway is responsible for routing a request to the right
shard, or fanning a query out to all shards and merging results.

This models how Nykaa's catalog/search tier partitions a huge product
catalog across many nodes/index-shards instead of one giant database.

Usage:
    python catalog_server.py catalog-1
    python catalog_server.py catalog-2
    python catalog_server.py catalog-3
"""

import sys
import os
import socket
import threading
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from common import config
from common.protocol import send_msg, recv_msg
from common.consistent_hash import ConsistentHashRing
from catalog_service.products_data import ALL_PRODUCTS


def partition_for_node(node_id: str) -> dict:
    """Build the ring from ALL configured catalog nodes, then keep only the
    products this node_id owns."""
    ring = ConsistentHashRing(nodes=list(config.CATALOG_NODES.keys()))
    owned = {
        p["product_id"]: p
        for p in ALL_PRODUCTS
        if ring.get_node(p["product_id"]) == node_id
    }
    return owned


class CatalogServer:
    def __init__(self, node_id: str):
        if node_id not in config.CATALOG_NODES:
            raise ValueError(f"Unknown catalog node '{node_id}'. "
                              f"Valid: {list(config.CATALOG_NODES)}")
        self.node_id = node_id
        self.bind_host = config.BIND_HOST
        self.port = config.CATALOG_NODES[node_id]["port"]
        self.products = partition_for_node(node_id)
        self.lock = threading.Lock()

    def log(self, msg: str) -> None:
        print(f"[{self.node_id}] {msg}", flush=True)

    def handle_client(self, conn: socket.socket, addr) -> None:
        try:
            req = recv_msg(conn)
            action = req.get("action")

            if action == "PING":
                send_msg(conn, {"status": "OK", "node": self.node_id, "role": "catalog"})

            elif action == "GET":
                pid = req.get("product_id")
                with self.lock:
                    product = self.products.get(pid)
                if product:
                    send_msg(conn, {"status": "OK", "product": product, "shard": self.node_id})
                else:
                    send_msg(conn, {"status": "NOT_FOUND", "shard": self.node_id})

            elif action == "LIST":
                with self.lock:
                    items = list(self.products.values())
                send_msg(conn, {"status": "OK", "products": items, "shard": self.node_id})

            elif action == "SEARCH":
                keyword = (req.get("keyword") or "").lower()
                category = req.get("category")
                with self.lock:
                    items = list(self.products.values())
                results = []
                for p in items:
                    if category and p["category"].lower() != category.lower():
                        continue
                    if keyword and keyword not in p["name"].lower() and keyword not in p["brand"].lower():
                        continue
                    results.append(p)
                send_msg(conn, {"status": "OK", "products": results, "shard": self.node_id})

            elif action == "DECREMENT_STOCK":
                pid = req.get("product_id")
                qty = int(req.get("qty", 1))
                with self.lock:
                    product = self.products.get(pid)
                    if not product:
                        send_msg(conn, {"status": "NOT_FOUND", "shard": self.node_id})
                        return
                    if product["stock"] < qty:
                        send_msg(conn, {"status": "OUT_OF_STOCK", "shard": self.node_id})
                        return
                    product["stock"] -= qty
                send_msg(conn, {"status": "OK", "remaining_stock": product["stock"], "shard": self.node_id})

            elif action == "INCREMENT_STOCK":
                # Used when an order is cancelled: put the units back.
                pid = req.get("product_id")
                qty = int(req.get("qty", 1))
                with self.lock:
                    product = self.products.get(pid)
                    if not product:
                        send_msg(conn, {"status": "NOT_FOUND", "shard": self.node_id})
                        return
                    product["stock"] += qty
                send_msg(conn, {"status": "OK", "stock": product["stock"], "shard": self.node_id})

            else:
                send_msg(conn, {"status": "ERROR", "message": f"unknown action {action}"})

        except Exception as exc:
            self.log(f"error handling {addr}: {exc}")
        finally:
            conn.close()

    def serve_forever(self) -> None:
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((self.bind_host, self.port))
        server_sock.listen(50)
        self.log(f"Catalog shard '{self.node_id}' listening on "
                 f"{self.bind_host}:{self.port} — owns {len(self.products)} products: "
                 f"{sorted(self.products.keys())}")
        while True:
            conn, addr = server_sock.accept()
            t = threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True)
            t.start()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python catalog_server.py <node_id>  e.g. catalog-1")
        sys.exit(1)
    server = CatalogServer(sys.argv[1])
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\n[{sys.argv[1]}] shutting down.")
