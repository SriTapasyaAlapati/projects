"""
common/consistent_hash.py
--------------------------
A small consistent-hashing ring, used by the Gateway to decide *which*
catalog shard owns a given product_id, without a lookup table that would
need to be kept in sync everywhere.

Why consistent hashing (and not `hash(key) % num_shards`)?
Plain modulo hashing means adding/removing a single shard remaps almost
every key, which would force a full re-shuffle of the catalog on every
scale-out. Consistent hashing maps only ~1/N of the keys when a node is
added or removed, which is exactly the property that lets services like
Nykaa's catalog/search tier scale horizontally without a full re-index.

Each physical node gets several "virtual nodes" on the ring so that load
is spread evenly even with a small number of physical shards.
"""

import bisect
import hashlib


class ConsistentHashRing:
    def __init__(self, nodes=None, virtual_nodes: int = 100):
        self.virtual_nodes = virtual_nodes
        self.ring = {}            # hash_value -> node_id
        self.sorted_keys = []     # sorted list of hash_values, for bisect
        if nodes:
            for node in nodes:
                self.add_node(node)

    @staticmethod
    def _hash(key: str) -> int:
        return int(hashlib.md5(key.encode("utf-8")).hexdigest(), 16)

    def add_node(self, node_id: str) -> None:
        for i in range(self.virtual_nodes):
            vnode_key = f"{node_id}#vn{i}"
            h = self._hash(vnode_key)
            self.ring[h] = node_id
            bisect.insort(self.sorted_keys, h)

    def remove_node(self, node_id: str) -> None:
        for i in range(self.virtual_nodes):
            vnode_key = f"{node_id}#vn{i}"
            h = self._hash(vnode_key)
            if h in self.ring:
                del self.ring[h]
                idx = bisect.bisect_left(self.sorted_keys, h)
                if idx < len(self.sorted_keys) and self.sorted_keys[idx] == h:
                    self.sorted_keys.pop(idx)

    def get_node(self, key: str) -> str:
        """Return the node_id responsible for `key` (e.g. a product_id)."""
        if not self.ring:
            raise RuntimeError("consistent hash ring is empty")
        h = self._hash(key)
        idx = bisect.bisect(self.sorted_keys, h)
        if idx == len(self.sorted_keys):
            idx = 0  # wrap around the ring
        return self.ring[self.sorted_keys[idx]]
