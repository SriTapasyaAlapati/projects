"""Integration tests: the LRU+TTL cache inside the gateways."""
import time
import pytest
from tests.conftest import call, shard_call, wait_until


def cache_totals():
    gws = call("STATUS")["gateways"].values()
    return {k: sum(g["cache"][k] for g in gws) for k in ("hits", "misses", "invalidations")}


def test_repeated_reads_produce_cache_hits(stack):
    call("LIST_CATALOG"); call("LIST_CATALOG")               # warm both gateways
    before = cache_totals()
    for _ in range(6):
        call("LIST_CATALOG")
    after = cache_totals()
    assert after["hits"] - before["hits"] == 6
    assert after["misses"] == before["misses"]


def test_background_polls_do_not_distort_cache_statistics(stack):
    call("LIST_CATALOG"); call("LIST_CATALOG")
    before = cache_totals()
    for _ in range(6):
        call("LIST_CATALOG", poll=True)
    assert cache_totals() == before


def test_stock_change_invalidates_cache_on_both_gateways(stack, user):
    pid = "P004"
    for _ in range(4):
        call("GET_PRODUCT", product_id=pid)                  # warm both gateways' caches
    start = call("GET_PRODUCT", product_id=pid)["product"]["stock"]
    call("ADD_TO_CART", user_id=user, product_id=pid, qty=2)
    assert call("CHECKOUT", user_id=user)["status"] == "OK"
    reads = [call("GET_PRODUCT", product_id=pid)["product"]["stock"] for _ in range(6)]
    assert reads == [start - 2] * 6, reads                   # never a stale value from either gateway


def test_invalidation_counter_increments_on_both_gateways(stack, user):
    before = {n: g["cache"]["invalidations"] for n, g in call("STATUS")["gateways"].items()}
    call("ADD_TO_CART", user_id=user, product_id="P010", qty=1)
    call("CHECKOUT", user_id=user)
    after = {n: g["cache"]["invalidations"] for n, g in call("STATUS")["gateways"].items()}
    assert all(after[n] > before[n] for n in before)         # the gateway that acted AND its peer


def test_add_to_cart_stock_check_bypasses_a_stale_cache(stack, user):
    """The cache may show old stock, but the decision to accept an add must use live stock."""
    pid = "P016"
    for _ in range(4):
        call("GET_PRODUCT", product_id=pid)                  # cache says plenty in stock
    live = shard_call(pid, action="GET")["product"]["stock"]
    taken = live - 1                                         # someone else buys nearly everything,
    assert shard_call(pid, action="DECREMENT_STOCK", qty=taken)["status"] == "OK"   # bypassing the gateways
    try:
        r = call("ADD_TO_CART", user_id=user, product_id=pid, qty=2)
        assert r["status"] == "OUT_OF_STOCK" and r["available_stock"] == 1
    finally:
        shard_call(pid, action="INCREMENT_STOCK", qty=taken)  # put it back


def test_ttl_is_the_safety_net_if_an_invalidation_is_missed(stack):
    """Change stock behind the gateways' backs (no invalidation message). Cached
    reads may be stale, but after the TTL (1.5 s in the test system) both are fresh."""
    from common import config
    if config.CACHE_TTL_SEC > 3:
        pytest.skip(f"needs a short TTL (this system uses {config.CACHE_TTL_SEC}s); "
                    "start it with CACHE_TTL_SEC=1.5 or let the test suite start its own copy")
    pid = "P018"
    for _ in range(4):
        call("GET_PRODUCT", product_id=pid)
    base = shard_call(pid, action="GET")["product"]["stock"]
    shard_call(pid, action="DECREMENT_STOCK", qty=3)
    try:
        time.sleep(1.8)
        fresh = [call("GET_PRODUCT", product_id=pid)["product"]["stock"] for _ in range(4)]
        assert fresh == [base - 3] * 4, fresh
    finally:
        shard_call(pid, action="INCREMENT_STOCK", qty=3)
        time.sleep(1.8)
