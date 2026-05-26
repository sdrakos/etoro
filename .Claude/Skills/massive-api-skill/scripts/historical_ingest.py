"""
historical_ingest.py — Ingest historical OHLCV from Massive into Supabase or CSV.

Pipeline pattern for building a local price database for backtesting.

Usage:
    # Ingest single ticker to CSV
    python historical_ingest.py --ticker AAPL --start 2020-01-01 --end 2024-12-31 --output csv

    # Ingest watchlist to Supabase
    python historical_ingest.py --tickers AAPL MSFT NVDA --start 2020-01-01 --end 2024-12-31 \\
        --output supabase --table prices_daily

    # Ingest full S&P 500
    python historical_ingest.py --universe sp500 --start 2020-01-01 --end 2024-12-31 \\
        --output supabase

Requirements:
    pip install massive pandas supabase
    export MASSIVE_API_KEY="your_key"
    export SUPABASE_URL="https://xxx.supabase.co"
    export SUPABASE_SERVICE_KEY="your_service_key"

Schema (Supabase):
    create table prices_daily (
        ticker text not null,
        date date not null,
        open numeric, high numeric, low numeric, close numeric,
        volume bigint, vwap numeric, transactions integer,
        primary key (ticker, date)
    );
    create index idx_prices_date on prices_daily(date);
"""

import os
import sys
import argparse
import time
import pandas as pd
from massive import RESTClient


# S&P 500 sample (use full list from your universe table in production)
SP500_SAMPLE = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "GOOG", "AMZN", "META", "BRK.B", "TSLA",
    "AVGO", "LLY", "JPM", "V", "UNH", "WMT", "XOM", "MA", "PG", "JNJ", "HD",
    "COST", "ORCL", "ABBV", "BAC", "KO", "MRK", "CVX", "CRM", "PEP", "ACN",
]


def fetch_ohlcv(client, ticker, start, end):
    """Fetch daily OHLCV bars for one ticker."""
    aggs = list(client.list_aggs(ticker, 1, "day", start, end, limit=50000))
    rows = []
    for a in aggs:
        rows.append({
            "ticker": ticker,
            "date": pd.to_datetime(a.timestamp, unit="ms").date().isoformat(),
            "open": a.open,
            "high": a.high,
            "low": a.low,
            "close": a.close,
            "volume": int(a.volume) if a.volume else None,
            "vwap": a.vwap,
            "transactions": a.transactions,
        })
    return rows


def write_csv(rows, output_dir="./data"):
    """Write rows to a single CSV partitioned by ticker."""
    os.makedirs(output_dir, exist_ok=True)
    df = pd.DataFrame(rows)
    if df.empty:
        return
    for ticker, group in df.groupby("ticker"):
        path = f"{output_dir}/{ticker}.csv"
        group.to_csv(path, index=False)
        print(f"  Wrote {len(group)} rows → {path}")


def write_supabase(rows, table_name="prices_daily"):
    """Upsert rows to Supabase table. Requires `supabase` package."""
    try:
        from supabase import create_client
    except ImportError:
        print("Install: pip install supabase")
        sys.exit(1)

    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    sb = create_client(url, key)

    # Batch upsert (1000 rows per call)
    BATCH = 1000
    for i in range(0, len(rows), BATCH):
        batch = rows[i:i + BATCH]
        sb.table(table_name).upsert(batch).execute()
        print(f"  Upserted batch {i // BATCH + 1} ({len(batch)} rows)")


def main():
    parser = argparse.ArgumentParser(description="Ingest historical prices from Massive")
    parser.add_argument("--ticker", help="Single ticker (e.g. AAPL)")
    parser.add_argument("--tickers", nargs="+", help="Multiple tickers")
    parser.add_argument("--universe", choices=["sp500"], help="Pre-defined universe")
    parser.add_argument("--start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD")
    parser.add_argument("--output", choices=["csv", "supabase"], default="csv")
    parser.add_argument("--table", default="prices_daily", help="Supabase table name")
    parser.add_argument("--output-dir", default="./data", help="CSV output dir")
    parser.add_argument("--sleep", type=float, default=0.0, help="Seconds between tickers (rate limit)")

    args = parser.parse_args()

    # Determine ticker list
    if args.ticker:
        tickers = [args.ticker]
    elif args.tickers:
        tickers = args.tickers
    elif args.universe == "sp500":
        tickers = SP500_SAMPLE  # extend with full list in production
    else:
        print("Must specify --ticker, --tickers, or --universe")
        sys.exit(1)

    client = RESTClient()
    print(f"Ingesting {len(tickers)} tickers from {args.start} to {args.end}")

    for i, ticker in enumerate(tickers, 1):
        print(f"\n[{i}/{len(tickers)}] {ticker}")
        try:
            rows = fetch_ohlcv(client, ticker, args.start, args.end)
            print(f"  Fetched {len(rows)} bars")
            if not rows:
                continue

            if args.output == "csv":
                write_csv(rows, args.output_dir)
            elif args.output == "supabase":
                write_supabase(rows, args.table)
        except Exception as e:
            print(f"  Error: {e}")

        if args.sleep:
            time.sleep(args.sleep)

    print("\nDone.")


if __name__ == "__main__":
    main()
