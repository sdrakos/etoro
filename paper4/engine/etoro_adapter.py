"""Thin wrapper over the eToro client (injected). Reads/normalizes demo positions, fetches daily
candles, and submits market orders. Execution is refused unless allow_execute=True (demo only,
this phase)."""
from __future__ import annotations

SEG = "demo"   # demo segment only, this phase


class EtoroAdapter:
    def __init__(self, client, allow_execute=False):
        self.client = client
        self.allow_execute = allow_execute

    def positions(self):
        data = self.client.request("GET", f"/api/v1/trading/info/{SEG}/portfolio")
        raw = ((data or {}).get("clientPortfolio") or {}).get("positions") or []
        out = []
        for p in raw:
            iid = p.get("instrumentID")
            if iid is None:
                continue
            out.append({"instrument_id": int(iid), "is_buy": bool(p.get("isBuy")),
                        "amount_eur": float(p.get("amount") or 0.0),
                        "position_id": p.get("positionID")})
        return out

    def candles(self, instrument_id, count=500, interval="OneDay"):
        return self.client.request(
            "GET",
            f"/api/v1/market-data/instruments/{instrument_id}/history/candles/desc/{interval}/{count}")

    def submit(self, order):
        if not self.allow_execute:
            raise PermissionError("execution disabled (pass --execute; demo only)")
        if order.action == "open":
            path = f"/api/v1/trading/execution/{SEG}/market-open-orders/by-amount"
            body = {"instrumentId": order.instrument_id, "isBuy": order.is_buy,
                    "amount": order.amount_eur}
        else:  # close — eToro closes by positionID at the positions/{id} route
            path = f"/api/v1/trading/execution/{SEG}/market-close-orders/positions/{order.position_id}"
            body = {}
        return self.client.request("POST", path, json=body)
