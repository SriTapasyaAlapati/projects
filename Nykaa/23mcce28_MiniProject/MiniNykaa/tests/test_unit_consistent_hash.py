"""Unit tests for common/consistent_hash.py."""
from common.consistent_hash import ConsistentHashRing

KEYS = [f"P{n:04d}" for n in range(1000)]


def test_same_key_always_maps_to_same_node():
    r = ConsistentHashRing(["n1", "n2", "n3"])
    assert all(r.get_node(k) == r.get_node(k) for k in KEYS)


def test_every_node_receives_a_fair_share():
    r = ConsistentHashRing(["n1", "n2", "n3"])
    counts = {}
    for k in KEYS:
        counts[r.get_node(k)] = counts.get(r.get_node(k), 0) + 1
    assert set(counts) == {"n1", "n2", "n3"}
    assert all(200 < v < 470 for v in counts.values()), counts      # roughly 333 each


def test_adding_a_node_moves_only_a_fraction_of_keys():
    before = ConsistentHashRing(["n1", "n2", "n3"])
    after = ConsistentHashRing(["n1", "n2", "n3", "n4"])
    moved = sum(1 for k in KEYS if before.get_node(k) != after.get_node(k))
    assert moved < 0.40 * len(KEYS)                  # ideal is 25%; modulo hashing would move ~75%
    # and everything that moved went TO the new node, nothing shuffled between old nodes
    assert all(after.get_node(k) == "n4" for k in KEYS if before.get_node(k) != after.get_node(k))


def test_removing_a_node_only_remaps_that_nodes_keys():
    full = ConsistentHashRing(["n1", "n2", "n3"])
    less = ConsistentHashRing(["n1", "n2", "n3"])
    less.remove_node("n3")
    for k in KEYS:
        if full.get_node(k) != "n3":
            assert less.get_node(k) == full.get_node(k)
        assert less.get_node(k) != "n3"
