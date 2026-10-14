"""
gateway/health_monitor.py
--------------------------
Implements a simple heartbeat / failure-detector algorithm.

Every HEARTBEAT_INTERVAL_SEC seconds, a background thread sends a PING to
every known backend node. A node is considered UP as long as it answers
within HEARTBEAT_TIMEOUT_SEC. If it misses FAILOVER_THRESHOLD heartbeats in
a row, the monitor marks it DOWN; the Gateway's routing logic checks this
status before sending real traffic, so a dead node is quickly taken out of
rotation (for catalog shards) or triggers failover (for the order service).

This is the classic heartbeat failure-detection pattern used throughout
distributed systems (cluster membership, Kubernetes liveness probes,
Cassandra's gossip failure detector, etc.) to decide "is this node still
alive?" without a human in the loop.
"""

import threading
import time

from common import config
from common.protocol import request as rpc_request


class HealthMonitor:
    def __init__(self, nodes: dict):
        """
        nodes: { node_name: {"host": ..., "port": ...} }
        """
        self.nodes = nodes
        self.lock = threading.Lock()
        self.status = {name: "UP" for name in nodes}          # UP / DOWN
        self.miss_count = {name: 0 for name in nodes}
        self._stop = False

    def is_up(self, node_name: str) -> bool:
        with self.lock:
            return self.status.get(node_name) == "UP"

    def mark_down(self, node_name: str) -> None:
        """Immediately mark a node DOWN (e.g. a live request to it just
        failed) instead of waiting for the next heartbeat round. The next
        successful heartbeat brings it back UP."""
        with self.lock:
            if self.status.get(node_name) != "DOWN":
                print(f"[health-monitor] {node_name} marked DOWN (request failed)", flush=True)
            self.status[node_name] = "DOWN"
            self.miss_count[node_name] = config.FAILOVER_THRESHOLD

    def snapshot(self) -> dict:
        with self.lock:
            return dict(self.status)

    def _check_once(self, node_name: str) -> None:
        addr = self.nodes[node_name]
        try:
            reply = rpc_request(addr["host"], addr["port"], {"action": "PING"},
                                 timeout=config.HEARTBEAT_TIMEOUT_SEC)
            ok = reply.get("status") == "OK"
        except Exception:
            ok = False

        with self.lock:
            if ok:
                self.miss_count[node_name] = 0
                if self.status[node_name] != "UP":
                    print(f"[health-monitor] {node_name} is back UP", flush=True)
                self.status[node_name] = "UP"
            else:
                self.miss_count[node_name] += 1
                if (self.miss_count[node_name] >= config.FAILOVER_THRESHOLD
                        and self.status[node_name] != "DOWN"):
                    print(f"[health-monitor] {node_name} marked DOWN "
                          f"after {self.miss_count[node_name]} missed heartbeats", flush=True)
                    self.status[node_name] = "DOWN"

    def _run(self) -> None:
        while not self._stop:
            for node_name in self.nodes:
                self._check_once(node_name)
            time.sleep(config.HEARTBEAT_INTERVAL_SEC)

    def start(self) -> None:
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def stop(self) -> None:
        self._stop = True
