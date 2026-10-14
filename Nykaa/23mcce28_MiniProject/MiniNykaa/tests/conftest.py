"""
tests/conftest.py - shared fixtures.

By default the test session launches its OWN copy of the whole system (3
catalog shards, 3 order replicas, 2 gateways, load balancer, web server) as
subprocesses on a separate port range, so it never collides with a copy you
already have running, and can KILL and RESTART nodes to test failover.

To test an already-running deployment instead (for example the Docker one):
    MININYKAA_EXTERNAL=1 pytest
In that mode nothing is started and tests marked "destructive" are skipped.
"""
import os
import sys
import time
import subprocess
import uuid

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

EXTERNAL = os.environ.get("MININYKAA_EXTERNAL") == "1"

if not EXTERNAL:
    # Private port range for the test system. Must be set BEFORE common.config
    # is imported, because config reads the environment at import time.
    os.environ.update({
        "GATEWAY_PORT": "15000", "GATEWAY_1_PORT": "15101", "GATEWAY_2_PORT": "15102",
        "CATALOG_1_PORT": "16001", "CATALOG_2_PORT": "16002", "CATALOG_3_PORT": "16003",
        "ORDER_1_PORT": "17001", "ORDER_2_PORT": "17002", "ORDER_3_PORT": "17003",
        "WEB_PORT": "18080", "WS_PORT": "18081",
        "CACHE_TTL_SEC": "1.5",          # short TTL so the TTL test is quick
        "LB_ALGO": "round_robin",
    })

from common import config                                  # noqa: E402
from common.protocol import request as rpc_request          # noqa: E402
from common.consistent_hash import ConsistentHashRing      # noqa: E402

PY = sys.executable
COMMANDS = {
    **{f"catalog-{i}": [PY, "catalog_service/catalog_server.py", f"catalog-{i}"] for i in (1, 2, 3)},
    **{f"order-{i}": [PY, "order_service/order_server.py", f"order-{i}"] for i in (1, 2, 3)},
    **{f"gateway-{i}": [PY, "gateway/gateway_server.py", f"gateway-{i}"] for i in (1, 2)},
    "lb": [PY, "gateway/load_balancer.py"],
    "web": [PY, "web/web_server.py"],
}
START_ORDER = ["catalog-1", "catalog-2", "catalog-3", "order-1", "order-2", "order-3",
               "gateway-1", "gateway-2", "lb", "web"]


def call(action, **kwargs):
    """One request through the load balancer (the system's front door)."""
    msg = {"action": action}
    msg.update(kwargs)
    return rpc_request(config.GATEWAY_HOST, config.GATEWAY_PORT, msg, timeout=20)


def node_call(node, **msg):
    """Talk directly to one order node, bypassing the gateways."""
    c = config.ORDER_NODES[node]
    return rpc_request(c["host"], c["port"], msg, timeout=5)


def shard_call(product_id, **msg):
    """Talk directly to the catalog shard that owns product_id."""
    ring = ConsistentHashRing(nodes=list(config.CATALOG_NODES))
    c = config.CATALOG_NODES[ring.get_node(product_id)]
    msg["product_id"] = product_id
    return rpc_request(c["host"], c["port"], msg, timeout=5)


def wait_until(predicate, timeout=15.0, interval=0.25, message="condition"):
    end = time.time() + timeout
    last = None
    while time.time() < end:
        try:
            last = predicate()
            if last:
                return last
        except Exception as exc:       # node may be mid-restart
            last = exc
        time.sleep(interval)
    raise AssertionError(f"timed out after {timeout}s waiting for {message} (last: {last!r})")


def fully_ready():
    st = call("STATUS")
    nodes, gws = st["nodes"], st["gateways"]
    return (all(g["state"] == "UP" for g in gws.values())
            and all(v == "UP" for k, v in nodes.items() if k != "active_order_node")
            and bool(nodes.get("active_order_node")))


class Stack:
    def __init__(self):
        self.procs = {}

    def start(self, name):
        self.procs[name] = subprocess.Popen(COMMANDS[name], cwd=ROOT, env=os.environ.copy(),
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if name.startswith("order"):
            time.sleep(0.2)

    def start_all(self):
        for name in START_ORDER:
            self.start(name)
            if name == "order-3":
                time.sleep(2.5)            # let the first election finish before gateways start
            if name == "gateway-2":
                time.sleep(1.0)

    def kill(self, name):
        p = self.procs.get(name)
        if p and p.poll() is None:
            p.kill()
            p.wait(timeout=5)

    def alive(self, name):
        p = self.procs.get(name)
        return p is not None and p.poll() is None

    def restore_all(self):
        for name in START_ORDER:
            if not self.alive(name):
                self.start(name)
        wait_until(fully_ready, timeout=30, message="whole system healthy again")

    def stop_all(self):
        for name in reversed(START_ORDER):
            self.kill(name)


@pytest.fixture(scope="session")
def stack():
    s = Stack()
    if EXTERNAL:
        wait_until(fully_ready, timeout=10, message="external system ready")
        yield s
        return
    s.start_all()
    try:
        wait_until(fully_ready, timeout=40, message="test system ready")
        yield s
    finally:
        s.stop_all()


@pytest.fixture
def restore(stack):
    """For destructive tests: skip on external systems, and always bring the
    system back to full health afterwards so later tests start clean."""
    if EXTERNAL:
        pytest.skip("destructive test: needs to kill processes (not available on an external system)")
    yield stack
    stack.restore_all()


@pytest.fixture
def user():
    return "u-" + uuid.uuid4().hex[:8]


@pytest.fixture
def web_url():
    return f"http://127.0.0.1:{config.WEB_PORT}"
