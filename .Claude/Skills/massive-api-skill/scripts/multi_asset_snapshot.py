"""
multi_asset_snapshot.py — Get unified snapshot across stocks/options/crypto/forex/indices.

Uses Massive's universal snapshot endpoint to monitor multiple asset classes
in a single API call. Useful for dashboards, cross-market monitoring,
diversified portfolio tracking.

Usage:
    # Default watchlist
    python multi_asset_snapshot.py

    # Custom mix
    python multi_asset_snapshot.py --tickers AAPL TSLA X:BTCUSD C:EURUSD I:SPX

    # JSON output
    python multi_asset_snapshot.py --output snapshot.json

    # Watch mode (refresh every N seconds)
    python multi_asset_snapshot.py --watch 30
"""

import argparse
import json
import time
from datetime import datetime
from massive import RESTClient


DEFAULT_WATCHLIST = [
    "AAPL", "MSFT", "NVDA", "TSLA",        # mega-cap tech
    "X:BTCUSD", "X:ETHUSD", "X:SOLUSD",    # crypto majors
    "C:EURUSD", "C:USDJPY",                # forex majors
    "I:SPX", "I:VIX",                      # indices
]


def asset_class(ticker):
    """Infer asset class from ticker prefix."""
    if ticker.startswith("X:"):
        return "crypto"
    if ticker.startswith("C:"):
        return "forex"
    if ticker.startswith("I:"):
        return "index"
    if ticker.startswith("O:"):
        return "option"
    return "stock"


def take_snapshot(tickers):
    """Fetch unified snapshot for all tickers."""
    client = RESTClient()
    snaps = list(client.list_universal_snapshots(ticker_any_of=tickers))

    out = []
    for s in snaps:
        # Universal snapshot has different fields per asset class
        record = {
            "ticker": s.ticker,
            "asset_class": asset_class(s.ticker),
            "type": getattr(s, "type", None),
            "last_price": None,
            "change_pct": None,
            "volume": None,
            "timestamp": datetime.now().isoformat(),
        }

        # Try common fields
        if hasattr(s, "value") and s.value is not None:
            record["last_price"] = s.value
        elif hasattr(s, "last_trade") and s.last_trade:
            record["last_price"] = getattr(s.last_trade, "price", None)
        elif hasattr(s, "last_quote") and s.last_quote:
            bid = getattr(s.last_quote, "bid", None)
            ask = getattr(s.last_quote, "ask", None)
            if bid and ask:
                record["last_price"] = (bid + ask) / 2

        if hasattr(s, "session") and s.session:
            record["change_pct"] = getattr(s.session, "change_percent", None)
            record["volume"] = getattr(s.session, "volume", None)

        out.append(record)

    return out


def render(snapshot):
    """Pretty-print snapshot table."""
    print(f"\n{'Ticker':<14}{'Asset':<10}{'Last':>14}{'Δ %':>10}{'Volume':>14}")
    print("─" * 62)
    for r in snapshot:
        last = f"{r['last_price']:>14.4f}" if r['last_price'] is not None else f"{'—':>14}"
        chg = f"{r['change_pct']:>9.2f}%" if r['change_pct'] is not None else f"{'—':>10}"
        vol = f"{r['volume']:>14,}" if r['volume'] is not None else f"{'—':>14}"
        print(f"{r['ticker']:<14}{r['asset_class']:<10}{last}{chg}{vol}")


def main():
    parser = argparse.ArgumentParser(description="Multi-asset snapshot monitor")
    parser.add_argument("--tickers", nargs="+", default=DEFAULT_WATCHLIST,
                        help="Tickers (any asset class, use prefixes X:, C:, I:, O:)")
    parser.add_argument("--output", help="Save JSON to file")
    parser.add_argument("--watch", type=int, default=0,
                        help="Refresh every N seconds (0=one-shot)")

    args = parser.parse_args()

    if args.watch > 0:
        try:
            while True:
                snapshot = take_snapshot(args.tickers)
                print(f"\n=== Snapshot at {datetime.now().isoformat()} ===")
                render(snapshot)
                if args.output:
                    with open(args.output, "w") as f:
                        json.dump(snapshot, f, indent=2)
                time.sleep(args.watch)
        except KeyboardInterrupt:
            print("\nStopped.")
    else:
        snapshot = take_snapshot(args.tickers)
        render(snapshot)
        if args.output:
            with open(args.output, "w") as f:
                json.dump(snapshot, f, indent=2)
            print(f"\nSaved → {args.output}")


if __name__ == "__main__":
    main()
