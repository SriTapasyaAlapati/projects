"""Integration tests: cart, stock validation, checkout, cancellation, concurrency."""
import threading
from tests.conftest import call, shard_call


def stock(pid):
    return shard_call(pid, action="GET")["product"]["stock"]


def test_add_update_remove_cart(stack, user):
    assert call("ADD_TO_CART", user_id=user, product_id="P003", qty=2)["cart"] == {"P003": 2}
    assert call("ADD_TO_CART", user_id=user, product_id="P003", qty=1)["cart"] == {"P003": 3}   # adds up
    assert call("UPDATE_CART", user_id=user, product_id="P003", qty=5)["cart"] == {"P003": 5}  # exact set
    assert call("UPDATE_CART", user_id=user, product_id="P003", qty=0)["cart"] == {}           # 0 removes
    call("ADD_TO_CART", user_id=user, product_id="P006", qty=1)
    assert call("REMOVE_FROM_CART", user_id=user, product_id="P006")["cart"] == {}


def test_cart_view_is_enriched_with_prices_and_totals(stack, user):
    call("ADD_TO_CART", user_id=user, product_id="P002", qty=2)      # Rs. 899 each
    v = call("VIEW_CART", user_id=user)
    assert v["items"][0]["subtotal"] == 1798 and v["total"] == 1798 and v["items"][0]["in_stock"] is True


def test_cannot_add_more_than_stock_even_cumulatively(stack, user):
    have = stock("P005")
    r = call("ADD_TO_CART", user_id=user, product_id="P005", qty=have + 1)
    assert r["status"] == "OUT_OF_STOCK" and "left in stock" in r["message"]
    assert call("ADD_TO_CART", user_id=user, product_id="P005", qty=have)["status"] == "OK"
    again = call("ADD_TO_CART", user_id=user, product_id="P005", qty=1)       # cart already holds it all
    assert again["status"] == "OUT_OF_STOCK"
    assert call("UPDATE_CART", user_id=user, product_id="P005", qty=have + 1)["status"] == "OUT_OF_STOCK"


def test_checkout_reduces_stock_and_clears_cart(stack, user):
    before = stock("P007")
    call("ADD_TO_CART", user_id=user, product_id="P007", qty=3)
    r = call("CHECKOUT", user_id=user)
    assert r["status"] == "OK" and r["order"]["status"] == "CONFIRMED" and r["order"]["total_amount"] == 499 * 3
    assert stock("P007") == before - 3
    assert call("VIEW_CART", user_id=user)["cart"] == {}
    assert [o["order_id"] for o in call("VIEW_ORDERS", user_id=user)["orders"]] == [r["order"]["order_id"]]


def test_checkout_of_empty_cart_is_rejected(stack, user):
    assert call("CHECKOUT", user_id=user)["status"] == "ERROR"


def test_cancel_returns_stock_and_second_cancel_is_rejected(stack, user):
    before = stock("P008")
    call("ADD_TO_CART", user_id=user, product_id="P008", qty=4)
    oid = call("CHECKOUT", user_id=user)["order"]["order_id"]
    assert stock("P008") == before - 4
    c = call("CANCEL_ORDER", user_id=user, order_id=oid)
    assert c["status"] == "OK" and c["order"]["status"] == "CANCELLED" and c["restocked"] == ["P008"]
    assert stock("P008") == before
    second = call("CANCEL_ORDER", user_id=user, order_id=oid)
    assert second["status"] == "ERROR"
    assert stock("P008") == before                                   # not restored twice
    assert call("VIEW_ORDERS", user_id=user)["orders"][0]["status"] == "CANCELLED"


def test_cancelling_an_unknown_order_is_not_found(stack, user):
    assert call("CANCEL_ORDER", user_id=user, order_id="ORD-DOESNOTEXIST")["status"] == "NOT_FOUND"


def test_users_have_separate_carts(stack):
    call("ADD_TO_CART", user_id="alice-t", product_id="P009", qty=1)
    assert call("VIEW_CART", user_id="bob-t")["cart"] == {}
    call("REMOVE_FROM_CART", user_id="alice-t", product_id="P009")


def test_concurrent_checkouts_give_unique_ids_and_exact_stock(stack):
    pid, n = "P011", 20
    before = stock(pid)
    ids, errors = [], []

    def shopper(i):
        u = f"conc-{i}-{threading.get_ident()}"
        try:
            call("ADD_TO_CART", user_id=u, product_id=pid, qty=1)
            ids.append(call("CHECKOUT", user_id=u)["order"]["order_id"])
        except Exception as exc:
            errors.append(exc)
    ts = [threading.Thread(target=shopper, args=(i,)) for i in range(n)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert not errors, errors
    assert len(ids) == n and len(set(ids)) == n                       # no duplicate order ids
    assert stock(pid) == before - n                                   # no lost or double decrements


def test_unknown_product_is_rejected(stack, user):
    assert call("ADD_TO_CART", user_id=user, product_id="NOPE", qty=1)["status"] == "OUT_OF_STOCK"


def test_search_and_list_return_merged_shard_results(stack):
    lst = call("LIST_CATALOG")
    assert len(lst["products"]) == 20 and set(lst["shards_used"]) == {"catalog-1", "catalog-2", "catalog-3"}
    serum = call("SEARCH_CATALOG", keyword="serum", category=None)["products"]
    assert {p["product_id"] for p in serum} == {"P002", "P004", "P013"}
    assert all(p["category"] == "Makeup" for p in call("SEARCH_CATALOG", keyword=None, category="Makeup")["products"])
