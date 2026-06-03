from unittest.mock import MagicMock, patch
import pytest
from fastapi import HTTPException


def _resp(status=200, json_body=None, text="", content=b"x"):
    r = MagicMock()
    r.status_code = status
    r.content = content
    r.text = text
    if json_body is None:
        r.json.side_effect = ValueError("no json")
    else:
        r.json.return_value = json_body
    return r


def test_request_uses_host_base_and_full_path():
    from etoro_api.client import EtoroClient, BASE_URL
    assert BASE_URL == "https://public-api.etoro.com"
    client = EtoroClient("PUB", "USR")
    with patch("etoro_api.client.httpx.Client") as Cli:
        ctx = Cli.return_value.__enter__.return_value
        ctx.request.return_value = _resp(200, {"ok": True})
        out = client.request("GET", "/api/v2/trading/info/orders:lookup", params={"a": 1})
    assert out == {"ok": True}
    args, kwargs = ctx.request.call_args
    assert args[0] == "GET"
    assert args[1] == "https://public-api.etoro.com/api/v2/trading/info/orders:lookup"
    h = kwargs["headers"]
    assert h["x-api-key"] == "PUB" and h["x-user-key"] == "USR"
    assert h["User-Agent"].startswith("Mozilla/")
    assert len(h["x-request-id"]) >= 8


def test_request_raises_httpexception_on_error_status():
    from etoro_api.client import EtoroClient
    client = EtoroClient("PUB", "USR")
    with patch("etoro_api.client.httpx.Client") as Cli:
        ctx = Cli.return_value.__enter__.return_value
        ctx.request.return_value = _resp(403, {"error": "1010"})
        with pytest.raises(HTTPException) as ei:
            client.request("GET", "/api/v1/watchlists")
    assert ei.value.status_code == 403


def test_drop_none_filters_none_values():
    from etoro_api.client import drop_none
    assert drop_none({"a": 1, "b": None, "c": "x"}) == {"a": 1, "c": "x"}
