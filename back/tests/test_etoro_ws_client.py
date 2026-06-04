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
