"""
common/lru_cache.py
--------------------
A thread-safe LRU cache with a per-entry TTL, used inside each gateway to
absorb repeated catalog reads (the same idea as Nykaa's documented
Memcached/Redis layer in front of its databases).

Two independent rules decide when an entry disappears:
  * LRU  - when the cache is full, the Least Recently Used entry is evicted
           to make room. Implemented with an OrderedDict: a hit moves the
           key to the "most recent" end; eviction pops the "oldest" end.
           get/set are O(1).
  * TTL  - every entry stores an expiry time; a read after that time counts
           as a miss and drops the entry (lazy expiry). TTL bounds how stale
           a value can ever be, even if an explicit invalidation is missed.

Counters (hits, misses, evictions, expirations, invalidations) are exposed
through stats() so the website's System tab can show the hit rate.
"""

import threading
import time
from collections import OrderedDict


class LRUCache:
    def __init__(self, capacity: int = 32, ttl: float = 10.0):
        self.capacity = capacity
        self.ttl = ttl
        self._data = OrderedDict()          # key -> (value, expires_at)
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.expirations = 0
        self.invalidations = 0

    def get(self, key, count=True):
        """Return (found, value). Expired entries count as misses.
        count=False is used for internal background polling so it does not
        distort the hit/miss statistics shown to the user."""
        now = time.time()
        with self._lock:
            item = self._data.get(key)
            if item is None:
                if count:
                    self.misses += 1
                return False, None
            value, expires_at = item
            if now >= expires_at:
                del self._data[key]
                if count:
                    self.expirations += 1
                    self.misses += 1
                return False, None
            self._data.move_to_end(key)     # mark as most recently used
            if count:
                self.hits += 1
            return True, value

    def set(self, key, value):
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
            self._data[key] = (value, time.time() + self.ttl)
            while len(self._data) > self.capacity:
                self._data.popitem(last=False)   # evict least recently used
                self.evictions += 1

    def clear(self):
        """Invalidate everything (called when stock changes)."""
        with self._lock:
            self._data.clear()
            self.invalidations += 1

    def stats(self) -> dict:
        with self._lock:
            total = self.hits + self.misses
            return {
                "size": len(self._data), "capacity": self.capacity, "ttl_sec": self.ttl,
                "hits": self.hits, "misses": self.misses,
                "hit_rate": round(100.0 * self.hits / total, 1) if total else 0.0,
                "evictions": self.evictions, "expirations": self.expirations,
                "invalidations": self.invalidations,
            }
