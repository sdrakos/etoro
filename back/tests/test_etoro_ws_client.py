import json
from etoro_api.ws_client import Tick, build_auth, build_subscribe, build_unsubscribe, parse_messages


def test_build_auth_shape():
    msg = build_auth("APIKEY", "USERKEY")
    assert msg["operation"] == "Authenticate"
    assert msg["data"] == {"userKey": "USERKEY", "apiKey": "APIKEY"}
    assert isinstance(msg["id"], str) and msg["id"]


def test_build_subscribe_topics_sorted_with_snapshot():
    msg = build_subscribe({100000, 1001})
    assert msg["operation"] == "Subscribe"
    assert msg["data"]["topics"] == ["instrument:1001", "instrument:100000"]
    assert msg["data"]["snapshot"] is True


def test_build_unsubscribe_no_snapshot():
    msg = build_unsubscribe({1001})
    assert msg["operation"] == "Unsubscribe"
    assert msg["data"]["topics"] == ["instrument:1001"]
    assert "snapshot" not in msg["data"]


def test_parse_messages_extracts_ticks():
    raw = {"messages": [
        {"topic": "instrument:100000", "type": "Trading.Instrument.Rate",
         "content": json.dumps({"Bid": 64990.0, "Ask": 65010.0, "LastExecution": 65000.0,
                                "Date": "2026-06-04T10:00:00Z"})},
        {"topic": "instrument:1", "type": "SomethingElse", "content": "{}"},  # ignored type
    ]}
    ticks = parse_messages(raw)
    assert len(ticks) == 1
    t = ticks[0]
    assert (t.instrument_id, t.bid, t.ask, t.last, t.ts) == (
        100000, 64990.0, 65010.0, 65000.0, "2026-06-04T10:00:00Z")


def test_parse_messages_skips_bad_content_and_empty():
    assert parse_messages({}) == []
    bad = {"messages": [{"topic": "instrument:5", "type": "Trading.Instrument.Rate",
                         "content": "not-json"}]}
    assert parse_messages(bad) == []


import asyncio
from etoro_api.ws_client import EtoroWsClient


class FakeWS:
    """In-memory websocket: records sent frames, yields canned incoming frames once."""
    def __init__(self, incoming):
        self.sent = []
        self._incoming = [json.dumps(x) for x in incoming]
        self.closed = False

    async def send(self, raw):
        self.sent.append(json.loads(raw))

    async def close(self):
        self.closed = True

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._incoming:
            return self._incoming.pop(0)
        raise StopAsyncIteration


def test_serve_authenticates_then_subscribes_active_then_emits_ticks():
    captured: list = []
    tick_frame = {"messages": [{"topic": "instrument:100000", "type": "Trading.Instrument.Rate",
                                "content": json.dumps({"Bid": 1.0, "Ask": 2.0, "LastExecution": 1.5,
                                                       "Date": "T"})}]}
    ws = FakeWS([tick_frame])
    client = EtoroWsClient("API", "USER")
    client._active = {100000}                      # pretend already subscribed
    client.on_tick(lambda t: captured.append(t))

    asyncio.run(client._serve(ws))

    assert ws.sent[0]["operation"] == "Authenticate"
    assert ws.sent[1]["operation"] == "Subscribe"
    assert ws.sent[1]["data"]["topics"] == ["instrument:100000"]
    assert len(captured) == 1 and captured[0].instrument_id == 100000
    assert client.last(100000).bid == 1.0


def test_subscribe_tracks_active_and_sends_when_connected():
    ws = FakeWS([])
    client = EtoroWsClient("API", "USER")
    client._ws = ws
    asyncio.run(client.subscribe({1001, 1002}))
    assert client._active == {1001, 1002}
    assert ws.sent[-1]["operation"] == "Subscribe"
    # subscribing the same ids again sends nothing new
    ws.sent.clear()
    asyncio.run(client.subscribe({1001}))
    assert ws.sent == []
