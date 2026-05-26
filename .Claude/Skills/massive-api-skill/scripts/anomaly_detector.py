"""
anomaly_detector.py — Detect unusual trade activity (z-score > threshold) in US stocks.

Based on Massive.com's "Hunting Anomalies in the Stock Market" tutorial.
Adapted for cleaner workflow + Supabase output option.

Usage:
    # 1. Build lookup table from flat files or REST
    python anomaly_detector.py build --start 2024-08-01 --end 2024-12-31

    # 2. Query anomalies for a specific date
    python anomaly_detector.py query --date 2024-10-18 --threshold 3.0

    # 3. Output to JSON for downstream consumption
    python anomaly_detector.py query --date 2024-10-18 --output anomalies.json

Requirements:
    pip install massive pandas
    export MASSIVE_API_KEY="your_key"

The strategy:
    For each ticker, compute rolling 5-day mean/std of trade count (transactions).
    Z-score = (today_trades - rolling_mean) / rolling_std
    If z > 3, it's a >99.7% statistical outlier → potential news/catalyst event.
"""

import os
import sys
import pickle
import json
import argparse
from collections import defaultdict
from datetime import date, timedelta, datetime
from typing import DefaultDict, Dict, Any

import pandas as pd
from massive import RESTClient


LOOKUP_PATH = "lookup_table.pkl"


def build_lookup_table(start_date: str, end_date: str, output_path: str = LOOKUP_PATH):
    """
    Build a lookup table of (ticker, date) → {trades, close, avg_trades, std_trades}
    Uses the grouped daily aggregates endpoint (one call per trading day).
    """
    client = RESTClient()
    trades_data = defaultdict(list)

    current = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()

    print(f"Fetching daily aggregates from {start_date} to {end_date}")
    while current <= end:
        # Skip weekends (holidays will return empty, which is fine)
        if current.weekday() < 5:
            print(f"  → {current.isoformat()}")
            try:
                aggs = client.get_grouped_daily_aggs(current.isoformat())
                for a in aggs:
                    trades_data[a.ticker].append({
                        "date": current,
                        "trades": a.transactions,
                        "close_price": a.close,
                    })
            except Exception as e:
                print(f"    error: {e}")
        current += timedelta(days=1)

    print(f"\nBuilding rolling statistics for {len(trades_data)} tickers")
    lookup_table: DefaultDict[str, Dict[str, Any]] = defaultdict(dict)

    for ticker, records in trades_data.items():
        df = pd.DataFrame(records).sort_values("date").set_index("date")
        df["price_diff"] = df["close_price"].pct_change() * 100
        df["trades_shifted"] = df["trades"].shift(1)
        df["avg_trades"] = df["trades_shifted"].rolling(window=5).mean()
        df["std_trades"] = df["trades_shifted"].rolling(window=5).std()

        for d, row in df.iterrows():
            date_str = d.strftime("%Y-%m-%d") if hasattr(d, 'strftime') else str(d)
            lookup_table[ticker][date_str] = {
                "trades": row["trades"],
                "close_price": row["close_price"],
                "price_diff": row["price_diff"] if pd.notnull(row["price_diff"]) else None,
                "avg_trades": row["avg_trades"] if pd.notnull(row["avg_trades"]) else None,
                "std_trades": row["std_trades"] if pd.notnull(row["std_trades"]) else None,
            }

    with open(output_path, "wb") as f:
        pickle.dump(dict(lookup_table), f)
    print(f"\nLookup table saved → {output_path}")


def query_anomalies(query_date: str, threshold: float = 3.0,
                    lookup_path: str = LOOKUP_PATH, output_path: str = None):
    """
    Query the lookup table for anomalies on a specific date.
    Returns sorted list of (ticker, z_score, trades, price_diff).
    """
    with open(lookup_path, "rb") as f:
        lookup_table = pickle.load(f)

    anomalies = []
    for ticker, date_data in lookup_table.items():
        if query_date not in date_data:
            continue
        d = date_data[query_date]
        if d["avg_trades"] is None or d["std_trades"] is None or d["std_trades"] == 0:
            continue
        z = (d["trades"] - d["avg_trades"]) / d["std_trades"]
        if z > threshold:
            anomalies.append({
                "ticker": ticker,
                "date": query_date,
                "z_score": round(z, 2),
                "trades": d["trades"],
                "avg_trades": round(d["avg_trades"], 0),
                "std_trades": round(d["std_trades"], 0),
                "close_price": d["close_price"],
                "price_diff_pct": round(d["price_diff"], 2) if d["price_diff"] else None,
            })

    anomalies.sort(key=lambda x: x["z_score"], reverse=True)

    print(f"\nFound {len(anomalies)} anomalies on {query_date} (z > {threshold})")
    print(f"{'Ticker':<8}{'Z-score':>10}{'Trades':>12}{'Avg':>12}{'Δ Price %':>12}")
    for a in anomalies[:30]:
        print(f"{a['ticker']:<8}{a['z_score']:>10}{a['trades']:>12}{int(a['avg_trades']):>12}"
              f"{(a['price_diff_pct'] or 0):>11.2f}%")

    if output_path:
        with open(output_path, "w") as f:
            json.dump(anomalies, f, indent=2)
        print(f"\nFull results saved → {output_path}")

    return anomalies


def main():
    parser = argparse.ArgumentParser(description="Detect volume anomalies in US stocks")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_build = sub.add_parser("build", help="Build lookup table")
    p_build.add_argument("--start", required=True, help="YYYY-MM-DD")
    p_build.add_argument("--end", required=True, help="YYYY-MM-DD")
    p_build.add_argument("--output", default=LOOKUP_PATH)

    p_query = sub.add_parser("query", help="Query anomalies for a date")
    p_query.add_argument("--date", required=True, help="YYYY-MM-DD")
    p_query.add_argument("--threshold", type=float, default=3.0)
    p_query.add_argument("--lookup", default=LOOKUP_PATH)
    p_query.add_argument("--output", default=None, help="Save results as JSON")

    args = parser.parse_args()

    if args.cmd == "build":
        build_lookup_table(args.start, args.end, args.output)
    elif args.cmd == "query":
        query_anomalies(args.date, args.threshold, args.lookup, args.output)


if __name__ == "__main__":
    main()
