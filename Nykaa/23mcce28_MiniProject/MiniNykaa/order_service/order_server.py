"""
order_service/order_server.py
------------------------------
Order/Cart microservice, run as a CLUSTER of three replicas
(order-1, order-2, order-3). There is no fixed primary: the replicas elect a
LEADER among themselves using the BULLY algorithm.

BULLY ALGORITHM (Garcia-Molina, 1982)
  Every node has a unique numeric id. The alive node with the HIGHEST id must
  be leader.
    1. A node that notices the leader is gone (or that has just started)
       starts an ELECTION: it sends ELECTION to every node with a HIGHER id.
    2. Any higher node that is alive replies ANSWER ("I'm alive, back off")
       and starts its own election.
    3. If nobody higher answers, the node WINS: it becomes leader and sends
       COORDINATOR (id) to everyone.
    4. A node that gets COORDINATOR records the new leader.
  A recovered high-id node simply starts an election, wins, and "bullies" the
  current leader out of the job - hence the name.

REPLICATION
  Only the leader accepts client reads/writes (others answer NOT_LEADER with
  a hint). The leader applies each write, bumps a version counter, and
  forwards it to every follower with that version. A follower that sees a gap
  in versions (it missed a write) pulls a full SNAPSHOT from the leader. A
  node that (re)starts pulls the highest-version snapshot from its peers
  BEFORE it takes part in an election, so a recovered high-id node cannot win
  with empty data.

KNOWN LIMITATIONS (documented, not hidden): Bully assumes reliable failure
detection - under a network partition two leaders could coexist (a term/epoch
number, as in Raft, would prevent that); replication is best-effort, so a
write acknowledged by a leader that crashes before forwarding it is lost.

Usage:
    python order_server.py order-1      (also order-2, order-3)
"""

import sys
import os
import socket
import threading
import time
import uuid

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from common import config
from common.protocol import send_msg, recv_msg, request as rpc_request


class OrderServer:
    def __init__(self, name: str):
        if name not in config.ORDER_NODES:
            raise ValueError(f"unknown order node '{name}'. Valid: {list(config.ORDER_NODES)}")
        me = config.ORDER_NODES[name]
        self.name = name
        self.id = me["id"]
        self.port = me["port"]
        self.bind_host = config.BIND_HOST
        self.peers = {n: c for n, c in config.ORDER_NODES.items() if n != name}

        self.state_lock = threading.RLock()     # guards carts/orders/version
        self.write_lock = threading.Lock()      # serialises apply+replicate on the leader
        self.carts = {}                         # user_id -> {product_id: qty}
        self.orders = {}                        # user_id -> [order, ...]
        self.version = 0                        # number of committed writes

        self.leader = None                      # name of the current leader, None = unknown
        self.election_lock = threading.Lock()
        self.election_running = False

    def log(self, msg):
        tag = "LEADER" if self.leader == self.name else ("follower" if self.leader else "no-leader")
        print(f"[{self.name}|id={self.id}|{tag}] {msg}", flush=True)

    @property
    def is_leader(self):
        return self.leader == self.name

    # ================================================================ state
    def apply_op(self, op):
        """Apply one write to local state. Returns (changed, result)."""
        t = op["type"]
        u = op.get("user_id")
        if t == "ADD_TO_CART":
            cart = self.carts.setdefault(u, {})
            cart[op["product_id"]] = cart.get(op["product_id"], 0) + op["qty"]
            return True, dict(cart)
        if t == "SET_CART_QTY":
            cart = self.carts.setdefault(u, {})
            if op["qty"] <= 0:
                cart.pop(op["product_id"], None)
            else:
                cart[op["product_id"]] = op["qty"]
            return True, dict(cart)
        if t == "PLACE_ORDER":
            order = {"order_id": op["order_id"], "user_id": u, "items": op["items"],
                     "total_amount": op["total_amount"], "status": "CONFIRMED"}
            self.orders.setdefault(u, []).append(order)
            self.carts[u] = {}
            return True, order
        if t == "CANCEL_ORDER":
            for o in self.orders.get(u, []):
                if o["order_id"] == op["order_id"]:
                    if o["status"] != "CONFIRMED":
                        return False, "ALREADY"
                    o["status"] = "CANCELLED"
                    return True, o
            return False, None
        raise ValueError(f"unknown op {t}")

    def snapshot(self):
        with self.state_lock:
            import copy
            return {"version": self.version, "carts": copy.deepcopy(self.carts),
                    "orders": copy.deepcopy(self.orders)}

    def install_snapshot(self, snap):
        with self.state_lock:
            if snap["version"] > self.version:
                self.carts, self.orders, self.version = snap["carts"], snap["orders"], snap["version"]
                return True
        return False

    def sync_from(self, peer_name):
        try:
            c = config.ORDER_NODES[peer_name]
            snap = rpc_request(c["host"], c["port"], {"action": "SNAPSHOT"}, timeout=2.0)
            if snap.get("status") == "OK" and self.install_snapshot(snap):
                self.log(f"synced state from {peer_name} (version {self.version})")
        except Exception:
            pass

    def sync_from_best_peer(self):
        """On startup: take the highest-version snapshot any peer has."""
        best, best_v = None, self.version
        for n, c in self.peers.items():
            try:
                r = rpc_request(c["host"], c["port"], {"action": "SNAPSHOT"}, timeout=1.5)
                if r.get("status") == "OK" and r["version"] > best_v:
                    best, best_v = r, r["version"]
            except Exception:
                pass
        if best and self.install_snapshot(best):
            self.log(f"startup sync: installed snapshot at version {self.version}")

    # ========================================================== replication
    def leader_commit(self, op):
        """Leader path: apply + replicate. Returns (changed, result)."""
        with self.write_lock:
            with self.state_lock:
                changed, result = self.apply_op(op)
                if changed:
                    self.version += 1
                version = self.version
            if changed:
                for n, c in self.peers.items():
                    try:
                        rpc_request(c["host"], c["port"],
                                    {"action": "REPLICATE", "op": op, "version": version,
                                     "from": self.name}, timeout=1.5)
                    except Exception as exc:
                        self.log(f"WARNING replicate to {n} failed ({exc.__class__.__name__}); "
                                 f"it will resync on its next write/snapshot")
        return changed, result

    def on_replicate(self, op, version, sender):
        with self.state_lock:
            if version <= self.version:
                return                                  # duplicate / old
            if version == self.version + 1:
                self.apply_op(op)
                self.version = version
                return
        # gap: we missed one or more writes -> pull everything from the sender
        self.sync_from(sender)

    # ============================================================== election
    def start_election(self):
        with self.election_lock:
            if self.election_running:
                return
            self.election_running = True
        try:
            while True:
                self.leader = None
                higher = [(n, c) for n, c in self.peers.items() if c["id"] > self.id]
                self.log(f"ELECTION started - asking higher ids: {[n for n, _ in higher] or 'none'}")
                got_answer = False
                for n, c in higher:
                    try:
                        r = rpc_request(c["host"], c["port"],
                                        {"action": "ELECTION", "from": self.name, "id": self.id},
                                        timeout=config.ELECTION_ANSWER_TIMEOUT_SEC)
                        if r.get("answer") == "ALIVE":
                            got_answer = True
                            self.log(f"ANSWER received from {n} - backing off")
                    except Exception:
                        pass
                if not got_answer:
                    self.become_leader()
                    return
                # a higher node is alive and is running its own election: wait for its COORDINATOR
                deadline = time.time() + config.COORDINATOR_WAIT_SEC
                while time.time() < deadline:
                    if self.leader is not None:
                        return
                    time.sleep(0.1)
                self.log("no COORDINATOR heard - restarting election")
        finally:
            with self.election_lock:
                self.election_running = False

    def become_leader(self):
        self.leader = self.name
        self.log("I WIN the election - announcing COORDINATOR to all peers")
        for n, c in self.peers.items():
            try:
                rpc_request(c["host"], c["port"],
                            {"action": "COORDINATOR", "leader": self.name, "id": self.id},
                            timeout=1.0)
            except Exception:
                pass

    def monitor_loop(self):
        """Followers ping the leader; a leaderless node (re)starts an election."""
        misses = 0
        while True:
            time.sleep(config.LEADER_PING_INTERVAL_SEC)
            leader = self.leader
            if leader is None:
                if not self.election_running:
                    threading.Thread(target=self.start_election, daemon=True).start()
                continue
            if leader == self.name:
                misses = 0
                continue
            c = config.ORDER_NODES[leader]
            try:
                rpc_request(c["host"], c["port"], {"action": "PING"}, timeout=config.LEADER_PING_TIMEOUT_SEC)
                misses = 0
            except Exception:
                misses += 1
                self.log(f"leader {leader} missed ping ({misses}/{config.LEADER_MISS_THRESHOLD})")
                if misses >= config.LEADER_MISS_THRESHOLD:
                    misses = 0
                    self.log(f"leader {leader} presumed DEAD")
                    threading.Thread(target=self.start_election, daemon=True).start()

    # ========================================================= request loop
    def handle_client(self, conn, addr):
        try:
            req = recv_msg(conn)
            a = req.get("action")

            # ---------------- cluster / election messages ----------------
            if a == "PING":
                return send_msg(conn, {"status": "OK", "node": self.name, "id": self.id, "leader": self.leader})
            if a == "WHO_LEADER":
                return send_msg(conn, {"status": "OK", "leader": self.leader, "is_leader": self.is_leader,
                                       "node": self.name, "id": self.id})
            if a == "ELECTION":
                send_msg(conn, {"status": "OK", "answer": "ALIVE", "id": self.id})
                if req.get("id", 0) < self.id:
                    threading.Thread(target=self.start_election, daemon=True).start()
                return
            if a == "COORDINATOR":
                if req["id"] < self.id:
                    # a LOWER node claims leadership while I am alive: bully it
                    send_msg(conn, {"status": "REJECT"})
                    threading.Thread(target=self.start_election, daemon=True).start()
                    return
                self.leader = req["leader"]
                self.log(f"COORDINATOR received: new leader is {self.leader}")
                send_msg(conn, {"status": "OK"})
                if self.leader != self.name:
                    threading.Thread(target=self.sync_from, args=(self.leader,), daemon=True).start()
                return
            if a == "SNAPSHOT":
                snap = self.snapshot()
                snap["status"] = "OK"
                return send_msg(conn, snap)
            if a == "REPLICATE":
                self.on_replicate(req["op"], req["version"], req.get("from"))
                return send_msg(conn, {"status": "OK"})

            # ---------------- client requests: leader only ----------------
            if not self.is_leader:
                return send_msg(conn, {"status": "NOT_LEADER", "leader": self.leader})

            if a == "ADD_TO_CART":
                _, cart = self.leader_commit({"type": "ADD_TO_CART", "user_id": req["user_id"],
                                              "product_id": req["product_id"], "qty": int(req.get("qty", 1))})
                send_msg(conn, {"status": "OK", "cart": cart})
            elif a in ("UPDATE_CART", "REMOVE_FROM_CART"):
                qty = 0 if a == "REMOVE_FROM_CART" else int(req.get("qty", 0))
                _, cart = self.leader_commit({"type": "SET_CART_QTY", "user_id": req["user_id"],
                                              "product_id": req["product_id"], "qty": qty})
                send_msg(conn, {"status": "OK", "cart": cart})
            elif a == "VIEW_CART":
                with self.state_lock:
                    cart = dict(self.carts.get(req["user_id"], {}))
                send_msg(conn, {"status": "OK", "cart": cart})
            elif a == "PLACE_ORDER":
                oid = f"ORD-{uuid.uuid4().hex[:10].upper()}"   # unique without coordination
                _, order = self.leader_commit({"type": "PLACE_ORDER", "user_id": req["user_id"],
                                               "order_id": oid, "items": req["items"],
                                               "total_amount": req["total_amount"]})
                send_msg(conn, {"status": "OK", "order": order})
            elif a == "CANCEL_ORDER":
                changed, result = self.leader_commit({"type": "CANCEL_ORDER", "user_id": req["user_id"],
                                                      "order_id": req["order_id"]})
                if changed:
                    send_msg(conn, {"status": "OK", "order": result})
                elif result == "ALREADY":
                    send_msg(conn, {"status": "ERROR", "message": "order is not cancellable (already cancelled)"})
                else:
                    send_msg(conn, {"status": "NOT_FOUND", "message": "order not found"})
            elif a == "VIEW_ORDERS":
                with self.state_lock:
                    orders = list(self.orders.get(req["user_id"], []))
                send_msg(conn, {"status": "OK", "orders": orders})
            else:
                send_msg(conn, {"status": "ERROR", "message": f"unknown action {a}"})
        except Exception as exc:
            self.log(f"error handling {addr}: {exc}")
        finally:
            conn.close()

    def serve_forever(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.bind_host, self.port))
        srv.listen(50)
        self.log(f"listening on {self.bind_host}:{self.port}")
        threading.Thread(target=self._boot, daemon=True).start()
        while True:
            conn, addr = srv.accept()
            threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True).start()

    def _boot(self):
        time.sleep(0.4)                 # let peers that start together open their sockets
        self.sync_from_best_peer()      # never win an election with empty data
        threading.Thread(target=self.monitor_loop, daemon=True).start()
        self.start_election()


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in config.ORDER_NODES:
        print("Usage: python order_server.py <order-1|order-2|order-3>")
        sys.exit(1)
    try:
        OrderServer(sys.argv[1]).serve_forever()
    except KeyboardInterrupt:
        print(f"\n[{sys.argv[1]}] shutting down.")
