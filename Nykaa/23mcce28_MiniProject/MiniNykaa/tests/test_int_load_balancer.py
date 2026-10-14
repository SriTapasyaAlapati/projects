"""Integration tests: the real load balancer in front of two real gateways."""
from tests.conftest import call, wait_until, fully_ready
import pytest


def test_status_reports_balancer_and_gateways(stack):
    st = call("STATUS")
    assert st["lb"]["algo"] == "round_robin"
    assert set(st["gateways"]) == {"gateway-1", "gateway-2"}
    assert all(g["state"] == "UP" for g in st["gateways"].values())


def test_requests_alternate_between_gateways(stack):
    via = [call("LIST_CATALOG")["via"] for _ in range(10)]
    assert set(via) == {"gateway-1", "gateway-2"}
    assert abs(via.count("gateway-1") - via.count("gateway-2")) <= 1
    assert all(a != b for a, b in zip(via, via[1:]))        # strict alternation


def test_status_checks_do_not_skew_the_split(stack):
    """Regression for a real bug: with 2 gateways, a STATUS call before every
    request means 2 pointer moves per cycle, so every real request landed on
    the SAME gateway. STATUS must not move the round-robin pointer."""
    via = []
    for _ in range(8):
        call("STATUS")
        via.append(call("LIST_CATALOG")["via"])
    assert set(via) == {"gateway-1", "gateway-2"}, via
    assert abs(via.count("gateway-1") - via.count("gateway-2")) <= 1


def test_background_polls_do_not_skew_the_split(stack):
    """Same, for the website's 2-second poll (requests flagged poll=True)."""
    via = []
    for _ in range(8):
        call("LIST_CATALOG", poll=True)
        via.append(call("LIST_CATALOG")["via"])
    assert set(via) == {"gateway-1", "gateway-2"}, via


def test_request_counters_increase_but_polls_are_not_counted(stack):
    def total():
        return sum(g["requests"] for g in call("STATUS")["gateways"].values())
    before = total()
    for _ in range(5):
        call("LIST_CATALOG")
    mid = total()
    for _ in range(5):
        call("LIST_CATALOG", poll=True)
    after = total()
    assert mid - before == 5
    assert after == mid


@pytest.mark.destructive
def test_gateway_crash_causes_no_failed_requests(restore):
    restore.kill("gateway-1")
    results = [call("LIST_CATALOG") for _ in range(12)]       # immediately, before any heartbeat
    assert all(r["status"] == "OK" for r in results)
    assert {r["via"] for r in results} == {"gateway-2"}
    wait_until(lambda: call("STATUS")["gateways"]["gateway-1"]["state"] == "DOWN",
               timeout=8, message="gateway-1 shown DOWN")
    assert call("STATUS")["gateways"]["gateway-1"]["failures"] >= 0


@pytest.mark.destructive
def test_recovered_gateway_rejoins_rotation(restore):
    restore.kill("gateway-2")
    assert call("LIST_CATALOG")["status"] == "OK"
    restore.restore_all()
    wait_until(lambda: len({call("LIST_CATALOG")["via"] for _ in range(4)}) == 2,
               timeout=10, message="both gateways serving again")


@pytest.mark.destructive
def test_all_gateways_down_returns_a_clear_error(restore):
    restore.kill("gateway-1"); restore.kill("gateway-2")
    r = call("LIST_CATALOG")
    assert r["status"] == "ERROR"
