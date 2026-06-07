"""Pull daily news TONE per product/theme from GDELT GKG via BigQuery — the cheap first test of
'does news sentiment add signal?' for the macro/ETF basket.

SAFETY FIRST: this ALWAYS shows the estimated bytes (dry-run) before running, and caps spend with
maximum_bytes_billed, so you can never accidentally scan terabytes off the 1 TB/month free tier.

Setup (one-time, you do it):
    pip install google-cloud-bigquery db-dtypes pandas
    gcloud auth application-default login        # interactive browser login (no client_secret file!)
Then:
    python paper4/news/gdelt_sentiment.py --project YOUR_PROJECT --from 2024-01-01 --to 2024-01-31 --dry-run
    python paper4/news/gdelt_sentiment.py --project YOUR_PROJECT --from 2024-01-01 --to 2024-01-31

NOTE (verify against GDELT docs — could not be tested from this environment):
 - Table: `gdelt-bq.gdeltv2.gkg_partitioned` is partitioned by _PARTITIONTIME and is MUCH cheaper to
   filter by date than the unpartitioned `gdelt-bq.gdeltv2.gkg`. Prefer the partitioned one.
 - `V2Tone` is comma-separated; the FIRST value is the average document tone.
 - THEME_FILTERS below are a STARTING POINT — refine the GKG theme codes against GDELT's theme list.
"""
from __future__ import annotations
import argparse
import os

# product -> a SQL LIKE filter on V2Themes/AllNames. Refine the theme codes against GDELT's list.
THEME_FILTERS = {
    "USO": "(V2Themes LIKE '%ENV_OIL%' OR V2Themes LIKE '%ECON_OIL%')",      # crude oil / energy
    "GLD": "(V2Themes LIKE '%ECON_GOLD%' OR AllNames LIKE '%gold price%')",  # gold
    "TLT": "(V2Themes LIKE '%ECON_INTEREST_RATE%' OR V2Themes LIKE '%WB_BOND%')",  # bonds / rates
    "UUP": "(V2Themes LIKE '%ECON_CENTRALBANK%' OR AllNames LIKE '%Federal Reserve%')",  # USD / Fed
    "SPY": "(V2Themes LIKE '%ECON_STOCKMARKET%')",                           # S&P 500 / equities
}

TABLE = "`gdelt-bq.gdeltv2.gkg_partitioned`"


def build_query(product, dt_from, dt_to):
    """Daily avg tone + article count for one product's theme over [from, to]."""
    where = THEME_FILTERS[product]
    return f"""
        SELECT
          DATE(_PARTITIONTIME) AS day,
          AVG(CAST(SPLIT(V2Tone, ',')[OFFSET(0)] AS FLOAT64)) AS avg_tone,
          COUNT(*) AS n_articles
        FROM {TABLE}
        WHERE _PARTITIONTIME BETWEEN TIMESTAMP('{dt_from}') AND TIMESTAMP('{dt_to}')
          AND V2Tone IS NOT NULL
          AND {where}
        GROUP BY day
        ORDER BY day
    """


def main():
    ap = argparse.ArgumentParser(description="GDELT GKG daily tone per product (BigQuery).")
    ap.add_argument("--project", required=True, help="your Google Cloud project id (the sandbox one)")
    ap.add_argument("--from", dest="from_", required=True, help="start date YYYY-MM-DD")
    ap.add_argument("--to", required=True, help="end date YYYY-MM-DD")
    ap.add_argument("--products", nargs="*", default=list(THEME_FILTERS))
    ap.add_argument("--max-gb", type=float, default=5.0, help="hard cap on bytes billed per query (GB)")
    ap.add_argument("--dry-run", action="store_true", help="estimate bytes only, run nothing")
    ap.add_argument("--out", default=None, help="output CSV path (default paper4/news/gdelt_tone.csv)")
    a = ap.parse_args()

    from google.cloud import bigquery   # imported here so --help works without the lib installed
    client = bigquery.Client(project=a.project)
    cap = int(a.max_gb * 1024 ** 3)

    frames = []
    for p in a.products:
        q = build_query(p, a.from_, a.to)
        if a.dry_run:
            cfg = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
            job = client.query(q, job_config=cfg)
            print(f"[{p}] would scan {job.total_bytes_processed/1024**3:.2f} GB "
                  f"({'OK' if job.total_bytes_processed <= cap else 'OVER CAP'})")
            continue
        cfg = bigquery.QueryJobConfig(maximum_bytes_billed=cap)
        df = client.query(q, job_config=cfg).to_dataframe()
        df["product"] = p
        print(f"[{p}] {len(df)} days, {a.from_}..{a.to}, "
              f"avg tone {df['avg_tone'].mean():.2f}, {int(df['n_articles'].sum())} articles")
        frames.append(df)

    if a.dry_run or not frames:
        return
    import pandas as pd
    out = a.out or os.path.join(os.path.dirname(__file__), "gdelt_tone.csv")
    panel = pd.concat(frames, ignore_index=True)
    panel.to_csv(out, index=False)
    print(f"\nsaved {out}  ({len(panel)} rows)  -> next: normalize, Δtone, gate, combine, leak-free backtest")


if __name__ == "__main__":
    main()
