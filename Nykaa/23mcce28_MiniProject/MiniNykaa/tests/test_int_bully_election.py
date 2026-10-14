"""Integration tests: Bully leader election among the three order replicas."""
import time
import pytest
from tests.conftest import call, node_call, wait_until


def leader():
    return call("STATUS")["nodes"]["active_order_node"]


def test_highest_id_is_leader_at_startup(stack):
    assert leader() == "order-3"
    for n in ("order-1", "order-2", "order-3"):
        assert node_call(n, action="WHO_LEADER")["leader"] == "order-3"      # all nodes agree


def test_followers_refuse_client_requests_and_point_to_the_leader(stack):
    for n in ("order-1", "order-2"):
        r = node_call(n, action="VIEW_CART", user_id="x")
        assert r["status"] == "NOT_LEADER" and r["leader"] == "order-3"
    assert node_call("order-3", action="VIEW_CART", user_id="x")["status"] == "OK"


def test_writes_are_replicated_to_followers(stack, user):
    call("ADD_TO_CART", user_id=user, product_id="P001", qty=2)
    v = node_call("order-3", action="SNAPSHOT")
    wait_until(lambda: node_call("order-1", action="SNAPSHOT")["version"] == v["version"]
               and node_call("order-2", action="SNAPSHOT")["version"] == v["version"],
               timeout=5, message="followers caught up")
    for n in ("order-1", "order-2"):
        assert node_call(n, action="SNAPSHOT")["carts"][user] == {"P001": 2}


@pytest.mark.destructive
def test_leader_crash_triggers_election_and_keeps_data(restore, user):
    call("ADD_TO_CART", user_id=user, product_id="P001", qty=3)
    restore.kill("order-3")
    new = wait_until(lambda: leader() == "order-2" and "order-2", timeout=15,
                     message="order-2 elected leader")
    assert new == "order-2"
    assert call("VIEW_CART", user_id=user)["cart"] == {"P001": 3}              # data survived
    r = call("ADD_TO_CART", user_id=user, product_id="P002", qty=1)            # and writes work
    assert r["status"] == "OK" and r["served_by"] == "order-2"


@pytest.mark.destructive
def test_recovered_node_resyncs_and_reclaims_leadership(restore, user):
    call("ADD_TO_CART", user_id=user, product_id="P001", qty=1)
    restore.kill("order-3")
    wait_until(lambda: leader() == "order-2", timeout=15, message="order-2 leads")
    call("ADD_TO_CART", user_id=user, product_id="P002", qty=2)                # written while order-3 is dead
    restore.start("order-3")
    wait_until(lambda: leader() == "order-3", timeout=20, message="order-3 bullies its way back")
    assert call("VIEW_CART", user_id=user)["cart"] == {"P001": 1, "P002": 2}    # it caught up first
    assert node_call("order-2", action="WHO_LEADER")["leader"] == "order-3"    # old leader stepped down


@pytest.mark.destructive
def test_cascading_failures_leave_the_last_node_leading(restore, user):
    call("ADD_TO_CART", user_id=user, product_id="P001", qty=1)
    restore.kill("order-3")
    wait_until(lambda: leader() == "order-2", timeout=15, message="order-2 leads")
    restore.kill("order-2")
    wait_until(lambda: leader() == "order-1", timeout=15, message="order-1 leads alone")
    assert call("VIEW_CART", user_id=user)["cart"] == {"P001": 1}
    assert call("ADD_TO_CART", user_id=user, product_id="P002", qty=1)["served_by"] == "order-1"


@pytest.mark.destructive
def test_a_non_leader_crash_does_not_change_the_leader(restore, user):
    restore.kill("order-1")
    time.sleep(3)
    assert leader() == "order-3"
    assert call("ADD_TO_CART", user_id=user, product_id="P001", qty=1)["status"] == "OK"
