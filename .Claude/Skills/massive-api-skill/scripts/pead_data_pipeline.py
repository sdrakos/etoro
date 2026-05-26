"""
pead_data_pipeline.py — Build PEAD (Post-Earnings Announcement Drift) features.

Computes:
- SUE (Standardized Unexpected Earnings) — needs an EPS estimate source
- EAR (Earnings Announcement Return) — uses Massive price data
- Composite rank score for strategy entry

Note: Massive provides actual EPS via income statements (TTM, quarterly).
Analyst consensus estimates are NOT in Massive — you need a complementary
source (Estimize, Zacks, FactSet, Refinitiv) OR derive a baseline from
prior quarters as a fallback.

This script implements the EAR side (pure Massive data) + a placeholder SUE
that uses 8-quarter-trailing-std as the standardization denominator.

Usage:
    python pead_data_pipeline.py --ticker AAPL --years 5
    python pead_data_pipeline.py --tickers AAPL MSFT NVDA --years 3 --output pead.csv

Reference:
    Bernard & Thomas (1989) — original PEAD discovery
    De Bondt & Thaler-style contrarian + Bernard underreaction
    Sloan (1996) — accruals component
"""

import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from massive import RESTClient


def fetch_earnings_history(client, ticker, years=5):
    """
    Fetch quarterly EPS history from income statements.
    Returns DataFrame with [filing_date, fiscal_period, eps_basic, eps_diluted].
    """
    rows = []
    for stmt in client.list_income_statements(ticker=ticker, timeframe="quarterly"):
        rows.append({
            "filing_date": stmt.filing_date,
            "fiscal_period": stmt.fiscal_period,
            "fiscal_year": stmt.fiscal_year,
            "eps_basic": getattr(stmt.financials.income_statement.basic_earnings_per_share, "value", None) if stmt.financials else None,
            "eps_diluted": getattr(stmt.financials.income_statement.diluted_earnings_per_share, "value", None) if stmt.financials else None,
        })
    df = pd.DataFrame(rows).sort_values("filing_date").reset_index(drop=True)
    # Limit to N years
    cutoff = (datetime.now() - timedelta(days=365 * years)).date().isoformat()
    df = df[df["filing_date"] >= cutoff].reset_index(drop=True)
    return df


def fetch_price_window(client, ticker, event_date, days_before=2, days_after=2):
    """
    Fetch daily bars around an event date.
    Returns DataFrame indexed by date.
    """
    start = (datetime.fromisoformat(event_date) - timedelta(days=days_before * 2)).date().isoformat()
    end = (datetime.fromisoformat(event_date) + timedelta(days=days_after * 2)).date().isoformat()
    aggs = list(client.list_aggs(ticker, 1, "day", start, end))
    if not aggs:
        return pd.DataFrame()
    df = pd.DataFrame([{
        "date": pd.to_datetime(a.timestamp, unit="ms").date(),
        "close": a.close,
    } for a in aggs]).set_index("date").sort_index()
    return df


def compute_ear(price_df, event_date, benchmark_return=0.0):
    """
    Earnings Announcement Return = cumulative return from [-1, +1] trading days
    around event date, minus benchmark return.

    For simplicity, benchmark_return = 0 (raw return).
    In production: pass SPY return for the same window.
    """
    event = datetime.fromisoformat(event_date).date()
    if price_df.empty:
        return None

    # Find nearest trading days
    dates = price_df.index.tolist()
    try:
        # Day before event
        before = max([d for d in dates if d < event])
        # Day after event
        after = min([d for d in dates if d > event])
    except ValueError:
        return None

    p_before = price_df.loc[before, "close"]
    p_after = price_df.loc[after, "close"]
    raw_return = (p_after - p_before) / p_before
    return raw_return - benchmark_return


def compute_sue(earnings_df, window=8):
    """
    Standardized Unexpected Earnings using seasonal random walk model.
    UE_t = EPS_t - EPS_{t-4}  (year-over-year same-quarter difference)
    SUE_t = UE_t / std(UE over trailing N quarters)
    """
    df = earnings_df.copy()
    df["eps"] = df["eps_diluted"].fillna(df["eps_basic"])
    df["eps_yoy"] = df["eps"].shift(4)  # same quarter prior year
    df["ue"] = df["eps"] - df["eps_yoy"]
    df["ue_std"] = df["ue"].rolling(window=window, min_periods=4).std()
    df["sue"] = df["ue"] / df["ue_std"]
    return df


def build_pead_dataset(ticker, years=5):
    """Build full PEAD feature dataset for one ticker."""
    client = RESTClient()
    print(f"\n=== {ticker} ===")

    earnings = fetch_earnings_history(client, ticker, years=years)
    if earnings.empty:
        print("  No earnings history")
        return pd.DataFrame()

    earnings = compute_sue(earnings)
    print(f"  Earnings events: {len(earnings)}")

    # Compute EAR for each earnings date
    ears = []
    for _, row in earnings.iterrows():
        prices = fetch_price_window(client, ticker, row["filing_date"])
        ear = compute_ear(prices, row["filing_date"])
        ears.append(ear)
    earnings["ear"] = ears

    # Composite rank (per-ticker, normalize within own history)
    earnings["sue_rank"] = earnings["sue"].rank(pct=True)
    earnings["ear_rank"] = earnings["ear"].rank(pct=True)
    earnings["composite"] = 0.5 * earnings["sue_rank"] + 0.5 * earnings["ear_rank"]
    earnings["ticker"] = ticker

    return earnings[["ticker", "filing_date", "fiscal_year", "fiscal_period",
                     "eps_basic", "eps_diluted", "ue", "sue", "ear",
                     "sue_rank", "ear_rank", "composite"]]


def main():
    parser = argparse.ArgumentParser(description="Build PEAD features from Massive data")
    parser.add_argument("--ticker", help="Single ticker")
    parser.add_argument("--tickers", nargs="+", help="Multiple tickers")
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--output", default="pead_features.csv")

    args = parser.parse_args()
    tickers = [args.ticker] if args.ticker else args.tickers
    if not tickers:
        print("Specify --ticker or --tickers")
        return

    all_dfs = []
    for ticker in tickers:
        df = build_pead_dataset(ticker, years=args.years)
        if not df.empty:
            all_dfs.append(df)

    if not all_dfs:
        print("No data collected.")
        return

    combined = pd.concat(all_dfs, ignore_index=True)
    combined.to_csv(args.output, index=False)
    print(f"\nSaved {len(combined)} rows → {args.output}")

    # Quick stats
    print("\nSUE distribution:")
    print(combined["sue"].describe())
    print("\nEAR distribution:")
    print(combined["ear"].describe())
    print("\nComposite top decile candidates (next quarter entry):")
    latest = combined.sort_values("filing_date").groupby("ticker").tail(1)
    print(latest.nlargest(10, "composite")[["ticker", "filing_date", "sue", "ear", "composite"]])


if __name__ == "__main__":
    main()
