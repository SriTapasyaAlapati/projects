"""
common/config.py
-----------------
Single source of truth for node addresses. In a real deployment this would
be service-discovery data (Consul/Eureka/DNS); here it is a small table
driven by environment variables, so the SAME code works two ways:

  * Locally across terminals: every node is 127.0.0.1 on its own port
    (the defaults below).
  * In Docker: docker-compose gives each service a DNS name on the compose
    network (e.g. "catalog-1", "order-2", "gateway-1"); each *_HOST env var
    below is set to that service name. A process still BINDS its listening
    socket to 0.0.0.0 inside its own container (BIND_HOST), but other nodes
    CONNECT to it using its service name.

Topology
    browser -> web -> LOAD BALANCER :5000 -> gateway-1 :5101 | gateway-2 :5102
                                      -> catalog-1..3 :6001-6003  (sharded)
                                      -> order-1..3   :7001-7003  (Bully leader)
"""

import os


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


def _env_float(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


# What a server process binds its own listening socket to. 0.0.0.0 inside a
# Docker container (so other containers can connect); 127.0.0.1 is fine for
# local single-machine runs.
BIND_HOST = _env("BIND_HOST", "127.0.0.1")
LOCAL = "127.0.0.1"

# The FRONT DOOR: what clients and the web bridge connect to. This is the
# load balancer, not a gateway.
GATEWAY_HOST = _env("GATEWAY_HOST", LOCAL)
GATEWAY_PORT = _env_int("GATEWAY_PORT", 5000)

# Gateway instances sitting behind the load balancer (stateless, so any of
# them can serve any request).
GATEWAY_NODES = {
    "gateway-1": {"host": _env("GATEWAY_1_HOST", LOCAL), "port": _env_int("GATEWAY_1_PORT", 5101)},
    "gateway-2": {"host": _env("GATEWAY_2_HOST", LOCAL), "port": _env_int("GATEWAY_2_PORT", 5102)},
}

# Load-balancing algorithm: "round_robin" or "least_connections"
LB_ALGO = _env("LB_ALGO", "round_robin")

# Catalog is sharded across these nodes using consistent hashing on product_id.
CATALOG_NODES = {
    "catalog-1": {"host": _env("CATALOG_1_HOST", LOCAL), "port": _env_int("CATALOG_1_PORT", 6001)},
    "catalog-2": {"host": _env("CATALOG_2_HOST", LOCAL), "port": _env_int("CATALOG_2_PORT", 6002)},
    "catalog-3": {"host": _env("CATALOG_3_HOST", LOCAL), "port": _env_int("CATALOG_3_PORT", 6003)},
}

# Order service: three replicas that elect a leader among themselves with
# the BULLY algorithm - the alive node with the HIGHEST id wins. There is no
# fixed primary any more.
ORDER_NODES = {
    "order-1": {"id": 1, "host": _env("ORDER_1_HOST", LOCAL), "port": _env_int("ORDER_1_PORT", 7001)},
    "order-2": {"id": 2, "host": _env("ORDER_2_HOST", LOCAL), "port": _env_int("ORDER_2_PORT", 7002)},
    "order-3": {"id": 3, "host": _env("ORDER_3_HOST", LOCAL), "port": _env_int("ORDER_3_PORT", 7003)},
}

HEARTBEAT_INTERVAL_SEC = 2.0     # gateway/LB -> backend health pings
HEARTBEAT_TIMEOUT_SEC = 1.0
FAILOVER_THRESHOLD = 2           # consecutive missed heartbeats before DOWN

# Bully election timing (order nodes)
LEADER_PING_INTERVAL_SEC = 1.0   # followers ping the leader this often
LEADER_PING_TIMEOUT_SEC = 0.8
LEADER_MISS_THRESHOLD = 2        # missed pings before a follower starts an election
ELECTION_ANSWER_TIMEOUT_SEC = 0.8
COORDINATOR_WAIT_SEC = 3.0       # wait for the winner's announcement after getting an ANSWER

# Gateway LRU cache
CACHE_CAPACITY = _env_int("CACHE_CAPACITY", 32)
CACHE_TTL_SEC = _env_float("CACHE_TTL_SEC", 10.0)

# Web bridge
WEB_PORT = _env_int("WEB_PORT", 8080)
WS_PORT = _env_int("WS_PORT", 8081)
