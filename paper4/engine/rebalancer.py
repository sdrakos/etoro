"""Pure rebalancing: current eToro positions + target weights -> list of Orders.
Close-and-reopen on a material change (market orders only, this phase); a minimum-trade
threshold suppresses tiny deltas. No IO."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Order:
    action: str          # "open" | "close"
    ticker: str
    instrument_id: int
    is_buy: bool
    amount_eur: float
    reason: str
    position_id: int | None = None   # set on "close" orders (eToro closes by positionID)


def _signed(positions):
    """({instrument_id: signed EUR}, {instrument_id: position_id}) from position dicts."""
    out, pid = {}, {}
    for p in positions:
        iid = int(p["instrument_id"])
        amt = float(p["amount_eur"]) * (1.0 if p["is_buy"] else -1.0)
        out[iid] = out.get(iid, 0.0) + amt
        if p.get("position_id") is not None:
            pid[iid] = p["position_id"]
    return out, pid


def plan(current_positions, target_weights, instrument_map, capital, min_trade=50.0):
    cur, pid = _signed(current_positions)
    id_to_ticker = {iid: tk for tk, iid in instrument_map.items()}
    orders = []
    target_ids = set()

    for ticker, w in target_weights.items():
        iid = instrument_map.get(ticker)
        if iid is None:
            continue
        iid = int(iid); target_ids.add(iid)
        tgt = w * capital
        have = cur.get(iid, 0.0)
        if abs(tgt - have) < min_trade:
            continue
        if abs(have) > 1e-9:
            orders.append(Order("close", ticker, iid, have > 0, abs(have), "rebalance",
                                position_id=pid.get(iid)))
        if abs(tgt) >= min_trade:
            orders.append(Order("open", ticker, iid, tgt > 0, abs(tgt), "rebalance"))

    for iid, have in cur.items():
        if iid not in target_ids and abs(have) >= min_trade:
            tk = id_to_ticker.get(iid, str(iid))
            orders.append(Order("close", tk, iid, have > 0, abs(have), "exit",
                                position_id=pid.get(iid)))
    return orders
