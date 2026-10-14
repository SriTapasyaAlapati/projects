"""
gateway/load_balancer.py
-------------------------
The FRONT DOOR. Every client request lands here first (port 5000) and is
handed to one of the gateway instances. Written directly on raw sockets,
like every other node.

ALGORITHMS (choose with the LB_ALGO environment variable)
  round_robin        gateways take turns in a fixed order. Fair when
                     requests cost about the same.
  least_connections  send to the gateway with the fewest requests currently
                     IN FLIGHT. Better when some requests (checkout) are far
                     slower than others (browse).

HEALTH-AWARE: the balancer heartbeats every gateway (same HealthMonitor the
gateways use for their backends) and never picks a DOWN one. If a forward
fails mid-request, that gateway is marked DOWN immediately and the request is
RETRIED on another gateway, so a gateway crash costs the user nothing.

The balancer is stateless per request, so it can itself be replicated. A
single balancer is still a single point of failure; in production it would be
a pair behind a virtual IP (keepalived/VRRP) or a cloud load balancer.

Usage:
    python load_balancer.py
"""

import sys
import os
import socket
import threading
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from common import config
from common.protocol import send_msg, recv_msg, request as rpc_request
from gateway.health_monitor import HealthMonitor


class LoadBalancer:
    def __init__(self, algo):
        if algo not in ("round_robin", "least_connections"):
            raise ValueError("LB_ALGO must be round_robin or least_connections")
        self.algo = algo
        self.names = list(config.GATEWAY_NODES)
        self.monitor = HealthMonitor(dict(config.GATEWAY_NODES))
        self.lock = threading.Lock()
        self.rr = 0
        self.requests = {n: 0 for n in self.names}     # forwarded so far
        self.inflight = {n: 0 for n in self.names}     # being served right now
        self.failures = {n: 0 for n in self.names}

    def log(self, msg):
        print(f"[lb] {msg}", flush=True)

    # ------------------------------------------------------------- choosing
    def pick(self, exclude=(), advance=True):
        """advance=False picks the next gateway WITHOUT moving the round-robin
        pointer. Internal/background requests (status checks, the website's
        2-second poll) use it; otherwise two requests per cycle would
        interact with a 2-gateway round-robin and every real request would
        land on the same gateway."""
        with self.lock:
            candidates = [n for n in self.names if n not in exclude and self.monitor.is_up(n)]
            if not candidates:
                candidates = [n for n in self.names if n not in exclude]   # last resort: try anyway
            if not candidates:
                return None
            if self.algo == "round_robin":
                choice = candidates[self.rr % len(candidates)]
                if advance:
                    self.rr += 1
            else:   # least_connections, ties broken round-robin
                low = min(self.inflight[n] for n in candidates)
                tied = [n for n in candidates if self.inflight[n] == low]
                choice = tied[self.rr % len(tied)]
                if advance:
                    self.rr += 1
            self.inflight[choice] += 1
            return choice

    def release(self, name):
        with self.lock:
            self.inflight[name] -= 1

    # ------------------------------------------------------------ forwarding
    def forward(self, req, count=True, advance=True):
        tried = []
        while True:
            name = self.pick(exclude=tried, advance=advance)
            if name is None:
                return {"status": "ERROR", "message": "no gateway available"}
            c = config.GATEWAY_NODES[name]
            try:
                reply = rpc_request(c["host"], c["port"], req, timeout=15.0)
                if count:
                    with self.lock:
                        self.requests[name] += 1
                reply.setdefault("via", name)
                return reply
            except Exception as exc:
                self.log(f"{name} failed ({exc.__class__.__name__}) - retrying on another gateway")
                with self.lock:
                    self.failures[name] += 1
                self.monitor.mark_down(name)
                tried.append(name)
            finally:
                self.release(name)

    def status(self):
        reply = self.forward({"action": "STATUS"}, count=False, advance=False)
        snap = self.monitor.snapshot()
        gws = {}
        for n in self.names:
            info = {"state": snap.get(n, "DOWN")}
            with self.lock:
                info.update(requests=self.requests[n], inflight=self.inflight[n], failures=self.failures[n])
            if info["state"] == "UP":
                try:
                    c = config.GATEWAY_NODES[n]
                    info["cache"] = rpc_request(c["host"], c["port"], {"action": "GATEWAY_INFO"}, timeout=1.0)["cache"]
                except Exception:
                    pass
            gws[n] = info
        reply["lb"] = {"algo": self.algo}
        reply["gateways"] = gws
        return reply

    # ------------------------------------------------------------ connection
    def handle_client(self, conn, addr):
        try:
            req = recv_msg(conn)
            if req.get("action") == "STATUS":
                send_msg(conn, self.status())
            elif req.get("poll"):                       # background poll: not counted, doesn't move round-robin
                send_msg(conn, self.forward(req, count=False, advance=False))
            else:
                send_msg(conn, self.forward(req))
        except Exception as exc:
            self.log(f"error handling {addr}: {exc}")
        finally:
            conn.close()

    def _summary_loop(self):
        """Print one line every 10 s, but only if traffic changed."""
        last = None
        while True:
            time.sleep(10)
            with self.lock:
                cur = dict(self.requests)
            if cur != last:
                self.log("requests forwarded so far: " + ", ".join(f"{n}={c}" for n, c in cur.items()))
                last = cur

    def serve_forever(self):
        self.monitor.start()
        threading.Thread(target=self._summary_loop, daemon=True).start()
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((config.BIND_HOST, config.GATEWAY_PORT))
        srv.listen(200)
        self.log(f"load balancer on {config.BIND_HOST}:{config.GATEWAY_PORT} "
                 f"algo={self.algo} -> {self.names}")
        while True:
            conn, addr = srv.accept()
            threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True).start()


if __name__ == "__main__":
    try:
        LoadBalancer(config.LB_ALGO).serve_forever()
    except KeyboardInterrupt:
        print("\n[lb] shutting down.")
