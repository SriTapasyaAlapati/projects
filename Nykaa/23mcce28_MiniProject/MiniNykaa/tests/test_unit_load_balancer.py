"""Unit tests for the load balancer's choosing logic (no sockets, no system)."""
import pytest
from gateway.load_balancer import LoadBalancer


def mk(algo="round_robin"):
    lb = LoadBalancer(algo)
    for n in lb.names:
        lb.monitor.status[n] = "UP"
    return lb


def test_round_robin_alternates():
    lb = mk()
    picks = []
    for _ in range(6):
        n = lb.pick(); picks.append(n); lb.release(n)
    assert picks == ["gateway-1", "gateway-2"] * 3


def test_round_robin_skips_a_down_gateway():
    lb = mk()
    lb.monitor.status["gateway-1"] = "DOWN"
    picks = []
    for _ in range(4):
        n = lb.pick(); picks.append(n); lb.release(n)
    assert picks == ["gateway-2"] * 4


def test_advance_false_does_not_move_the_pointer():
    """Background polling must not steal turns from real requests."""
    lb = mk()
    first = lb.pick(); lb.release(first)                 # gateway-1, pointer -> 1
    for _ in range(5):                                   # a burst of polls
        n = lb.pick(advance=False); lb.release(n)
    nxt = lb.pick(); lb.release(nxt)
    assert (first, nxt) == ("gateway-1", "gateway-2")    # real requests still alternate


def test_least_connections_prefers_the_idle_gateway():
    lb = mk("least_connections")
    lb.inflight = {"gateway-1": 3, "gateway-2": 0}
    assert lb.pick() == "gateway-2"


def test_least_connections_balances_as_load_grows():
    lb = mk("least_connections")
    lb.inflight = {"gateway-1": 2, "gateway-2": 0}
    got = [lb.pick() for _ in range(4)]                  # gw-2 until it catches up, then both
    assert got[:2] == ["gateway-2", "gateway-2"]
    assert set(got) == {"gateway-1", "gateway-2"}


def test_inflight_counter_is_released():
    lb = mk()
    n = lb.pick()
    assert lb.inflight[n] == 1
    lb.release(n)
    assert lb.inflight[n] == 0


def test_excluded_gateways_are_not_chosen_and_none_left_returns_none():
    lb = mk()
    assert lb.pick(exclude=["gateway-1"]) == "gateway-2"
    assert lb.pick(exclude=["gateway-1", "gateway-2"]) is None


def test_all_down_falls_back_to_trying_anyway():
    lb = mk()
    for n in lb.names:
        lb.monitor.status[n] = "DOWN"
    assert lb.pick() in lb.names


def test_unknown_algorithm_is_rejected():
    with pytest.raises(ValueError):
        LoadBalancer("random")
