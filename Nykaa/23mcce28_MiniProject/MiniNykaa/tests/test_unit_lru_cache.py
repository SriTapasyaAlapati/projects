"""Unit tests for common/lru_cache.py (no system needed)."""
import time
from common.lru_cache import LRUCache


def test_miss_then_hit():
    c = LRUCache(capacity=4, ttl=5)
    assert c.get("a") == (False, None)
    c.set("a", 1)
    assert c.get("a") == (True, 1)
    s = c.stats()
    assert (s["hits"], s["misses"]) == (1, 1) and s["hit_rate"] == 50.0


def test_evicts_least_recently_used():
    c = LRUCache(capacity=2, ttl=5)
    c.set("a", 1); c.set("b", 2)
    c.get("a")                       # a is now more recent than b
    c.set("c", 3)                    # over capacity -> b (the LRU) must go
    assert c.get("b")[0] is False
    assert c.get("a")[0] is True and c.get("c")[0] is True
    assert c.stats()["evictions"] == 1


def test_never_exceeds_capacity():
    c = LRUCache(capacity=3, ttl=5)
    for i in range(50):
        c.set(i, i)
    assert c.stats()["size"] == 3


def test_entries_expire_after_ttl():
    c = LRUCache(capacity=4, ttl=0.2)
    c.set("a", 1)
    assert c.get("a")[0] is True
    time.sleep(0.3)
    assert c.get("a") == (False, None)
    assert c.stats()["expirations"] == 1


def test_overwrite_refreshes_value_and_recency():
    c = LRUCache(capacity=2, ttl=5)
    c.set("a", 1); c.set("b", 2); c.set("a", 99); c.set("c", 3)   # b is LRU, not a
    assert c.get("a") == (True, 99) and c.get("b")[0] is False


def test_clear_counts_invalidation():
    c = LRUCache(capacity=4, ttl=5)
    c.set("a", 1); c.clear()
    assert c.get("a")[0] is False and c.stats()["invalidations"] == 1


def test_uncounted_reads_do_not_change_statistics():
    c = LRUCache(capacity=4, ttl=5)
    c.set("a", 1)
    c.get("a", count=False); c.get("zzz", count=False)
    s = c.stats()
    assert s["hits"] == 0 and s["misses"] == 0
