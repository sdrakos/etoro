import pytest
from rebalancer import Order
from etoro_adapter import EtoroAdapter


class FakeClient:
    def __init__(self): self.sent = []
    def request(self, method, path, **kw):
        if path.endswith("/portfolio"):
            return {"clientPortfolio": {"positions": [
                {"instrumentID": 101, "isBuy": True, "amount": 3000.0}]}}
        self.sent.append((method, path, kw)); return {"ok": True}


def test_positions_normalized():
    a = EtoroAdapter(FakeClient())
    pos = a.positions()
    assert pos == [{"instrument_id": 101, "is_buy": True, "amount_eur": 3000.0}]


def test_submit_refused_without_execute():
    a = EtoroAdapter(FakeClient(), allow_execute=False)
    with pytest.raises(PermissionError):
        a.submit(Order("open", "SPY", 101, True, 500.0, "rebalance"))


def test_submit_open_sends_request_when_allowed():
    c = FakeClient(); a = EtoroAdapter(c, allow_execute=True)
    a.submit(Order("open", "SPY", 101, True, 500.0, "rebalance"))
    assert len(c.sent) == 1
    method, path, kw = c.sent[0]
    assert method == "POST" and "market-open-orders" in path
