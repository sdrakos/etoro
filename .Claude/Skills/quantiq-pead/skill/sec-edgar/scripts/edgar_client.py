#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
edgar_client.py — minimal, well-behaved client for the SEC EDGAR REST APIs.

All endpoints are free and need NO API key. The only access requirements are:
  (1) a descriptive User-Agent header with your name + email, and
  (2) staying under ~10 requests/second.

Base URL: https://data.sec.gov/
Ticker->CIK map: https://www.sec.gov/files/company_tickers.json

Usage:
    from edgar_client import EdgarClient
    ec = EdgarClient("Your Name your@email.com")
    cik = ec.cik_for("AAPL")                         # -> '0000320193'
    facts = ec.company_facts("AAPL")                 # all XBRL facts (one JSON)
    df  = ec.concept_series("AAPL", "EarningsPerShareDiluted")  # tidy DataFrame
    subs = ec.submissions("AAPL")                    # filing history + dates

Returns pandas DataFrames where it makes sense; raw dicts otherwise.
"""

import time
import threading
import requests
import pandas as pd

BASE = "https://data.sec.gov"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"


class EdgarClient:
    def __init__(self, user_agent, max_rps=8, timeout=30, max_retries=4):
        if not user_agent or "@" not in user_agent:
            raise ValueError(
                "SEC requires a User-Agent with your name and email, e.g. "
                "'Stefanos Drakos stefanos@agelai.gr'. Requests without it get 403."
            )
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Host": "data.sec.gov",
        })
        self.timeout = timeout
        self.max_retries = max_retries
        self._min_interval = 1.0 / max_rps
        self._last = 0.0
        self._lock = threading.Lock()
        self._ticker_map = None

    # ---------- low-level GET with rate limiting + backoff ----------
    def _get(self, url, host=None):
        headers = {}
        if host:
            headers["Host"] = host
        for attempt in range(self.max_retries):
            with self._lock:
                wait = self._min_interval - (time.time() - self._last)
                if wait > 0:
                    time.sleep(wait)
                self._last = time.time()
            try:
                r = self.session.get(url, timeout=self.timeout, headers=headers or None)
            except requests.RequestException as e:
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(1.5 * (attempt + 1))
                continue
            if r.status_code == 200:
                return r.json()
            if r.status_code == 404:
                return None
            if r.status_code in (403, 429, 500, 502, 503):
                time.sleep(1.5 * (attempt + 1))  # backoff and retry
                continue
            r.raise_for_status()
        raise RuntimeError(f"EDGAR request failed after retries: {url}")

    # ---------- CIK resolution ----------
    def _load_tickers(self):
        # company_tickers.json lives on www.sec.gov, not data.sec.gov
        data = self._get(TICKERS_URL, host="www.sec.gov")
        m = {}
        for row in data.values():
            m[row["ticker"].upper()] = str(row["cik_str"]).zfill(10)
        self._ticker_map = m

    def cik_for(self, ticker):
        """Return the 10-digit zero-padded CIK for a ticker (e.g. 'AAPL'->'0000320193')."""
        if self._ticker_map is None:
            self._load_tickers()
        cik = self._ticker_map.get(ticker.upper())
        if cik is None:
            raise KeyError(f"No CIK found for ticker {ticker!r}")
        return cik

    def _norm_cik(self, ticker_or_cik):
        s = str(ticker_or_cik)
        if s.isdigit():
            return s.zfill(10)
        return self.cik_for(s)

    # ---------- raw endpoints ----------
    def company_facts(self, ticker_or_cik):
        """All XBRL facts a company ever filed (single JSON). Endpoint: /api/xbrl/companyfacts."""
        cik = self._norm_cik(ticker_or_cik)
        return self._get(f"{BASE}/api/xbrl/companyfacts/CIK{cik}.json")

    def company_concept(self, ticker_or_cik, tag, taxonomy="us-gaap"):
        """All disclosures for one concept (tag). Endpoint: /api/xbrl/companyconcept."""
        cik = self._norm_cik(ticker_or_cik)
        return self._get(f"{BASE}/api/xbrl/companyconcept/CIK{cik}/{taxonomy}/{tag}.json")

    def submissions(self, ticker_or_cik):
        """Filing history + metadata (form, filingDate, accession...). Endpoint: /submissions."""
        cik = self._norm_cik(ticker_or_cik)
        return self._get(f"{BASE}/submissions/CIK{cik}.json")

    def frames(self, tag, period, unit="USD", taxonomy="us-gaap"):
        """One fact across ALL companies for a period. Endpoint: /api/xbrl/frames.
        Example: frames('Revenues','CY2023Q4','USD'). Period codes: CY2023Q1, CY2023Q1I (instant)."""
        return self._get(f"{BASE}/api/xbrl/frames/{taxonomy}/{tag}/{unit}/{period}.json")

    # ---------- tidy helpers ----------
    def concept_series(self, ticker_or_cik, tag, taxonomy="us-gaap",
                       forms=("10-Q", "10-K"), keep="first_filed"):
        """
        Return a tidy DataFrame for one concept with the POINT-IN-TIME filing date.

        Columns: end (period end), val, fy, fp, form, filed, accn, unit, start.
        'filed' is the date the value became public -> use it for backtests (no look-ahead).

        keep:
          'first_filed' -> for each period 'end', keep the EARLIEST filing (original report,
                           the right choice for event-study/PEAD signal timing).
          'last_filed'  -> keep the latest (restated) value.
          'all'         -> keep every row (you dedup yourself).
        """
        js = self.company_concept(ticker_or_cik, tag, taxonomy)
        if not js or "units" not in js or not js["units"]:
            return pd.DataFrame()
        # pick the unit with the most observations (EPS is usually 'USD/shares')
        unit = max(js["units"].items(), key=lambda kv: len(kv[1]))[0]
        rows = js["units"][unit]
        df = pd.DataFrame(rows)
        df["unit"] = unit
        if "filed" in df:
            df["filed"] = pd.to_datetime(df["filed"])
        if "end" in df:
            df["end"] = pd.to_datetime(df["end"])
        if forms and "form" in df:
            df = df[df["form"].isin(forms)]
        df = df.dropna(subset=["val"]).sort_values(["end", "filed"])
        if keep == "first_filed":
            df = df.drop_duplicates(subset=["end"], keep="first")
        elif keep == "last_filed":
            df = df.drop_duplicates(subset=["end"], keep="last")
        cols = [c for c in ["end", "val", "fy", "fp", "form", "filed", "accn", "unit", "start"]
                if c in df.columns]
        return df[cols].reset_index(drop=True)

    def available_tags(self, ticker_or_cik, taxonomy="us-gaap"):
        """List every concept tag a company actually reports (helps with tag inconsistency)."""
        facts = self.company_facts(ticker_or_cik)
        if not facts:
            return []
        return sorted(facts.get("facts", {}).get(taxonomy, {}).keys())


if __name__ == "__main__":
    import sys
    ua = sys.argv[1] if len(sys.argv) > 1 else "Example User example@example.com"
    ec = EdgarClient(ua)
    print("AAPL CIK:", ec.cik_for("AAPL"))
    s = ec.concept_series("AAPL", "EarningsPerShareDiluted")
    print(s.tail(8).to_string(index=False))
