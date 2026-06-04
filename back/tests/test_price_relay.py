import asyncio
from etoro_api.ws_client import Tick
from routers.ws_prices import PriceRelay, compute_change


class FakeClient:
    """Stands in for EtoroWsClient: records sub/unsub, stores last, holds the tick cb."""
    def __init__(self):
        self.subbed, self.unsubbed = [], []
        self._cb = None
        self._last = {}
    def on_tick(self, cb): self._cb = cb
    def last(self, i): return self._last.get(int(i))
    async def subscribe(self, ids): self.subbed.append(set(ids))
    async def unsubscribe(self, ids): self.unsubbed.append(set(ids))
    async def emit(self, tick):
        self._last[tick.instrument_id] = tick
        r = self._cb(tick)
        if asyncio.iscoroutine(r): await r


class FakeBrowser:
    def __init__(self): self.sent = []
    async def send_json(self, obj): self.sent.append(obj)


def test_compute_change_and_absurd_guard():
    assert compute_change(110.0, 100.0) == 10.0
    assert compute_change(100.0, 100.0) == 0.0
    assert compute_change(100.0, None) is None
    assert compute_change(100.0, 0) is None
    assert compute_change(1000.0, 0.0001) is None   # absurd → None


def test_two_clients_overlapping_ids_subscribe_once_and_fanout():
    async def scenario():
        client = FakeClient()
        relay = PriceRelay(client, prev_close={100000: 100.0})
        a, b = FakeBrowser(), FakeBrowser()
        await relay.set_ids(a, {100000})
        await relay.set_ids(b, {100000})            # overlap → no second upstream subscribe
        assert client.subbed == [{100000}]
        await client.emit(Tick(100000, bid=1.0, ask=2.0, last=110.0, ts="T"))
        # fan-out to BOTH, with change% from prev_close
        assert a.sent[-1] == {"instrumentId": 100000, "bid": 1.0, "ask": 2.0,
                              "last": 110.0, "change_pct": 10.0, "ts": "T"}
        assert b.sent[-1]["instrumentId"] == 100000
    asyncio.run(scenario())


def test_refcount_zero_triggers_debounced_unsubscribe():
    import routers.ws_prices as mod
    async def scenario():
        client = FakeClient()
        relay = PriceRelay(client, prev_close={})
        a = FakeBrowser()
        await relay.set_ids(a, {7})
        assert client.subbed == [{7}]
        await relay.detach(a)                        # refcount 7 → 0
        await asyncio.sleep(0.05)                     # let the (tiny) debounce fire
        assert client.unsubbed == [{7}]
    mod.UNSUB_DEBOUNCE_S = 0.01                       # shrink debounce for the test
    asyncio.run(scenario())


def test_snapshot_sent_to_new_subscriber():
    async def scenario():
        client = FakeClient()
        client._last[100000] = Tick(100000, bid=5.0, ask=6.0, last=5.5, ts="T0")
        relay = PriceRelay(client, prev_close={100000: 5.0})
        a = FakeBrowser()
        await relay.set_ids(a, {100000})
        assert a.sent and a.sent[-1]["bid"] == 5.0    # immediate snapshot
    asyncio.run(scenario())
