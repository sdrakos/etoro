# Signal Engine + DER Risk Layer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Φέρε νέα ορθογώνια σήματα (PEAD earnings-surprise, sector-neutral momentum) από δωρεάν Yahoo data, πέρασέ τα από το Fundamental-Law gate (`IC_t>2`), και απόδειξε την «signal engine + DER risk layer» αρχιτεκτονική σε stressed walk-forward 2015-2024.

**Architecture:** Hybrid. Reuse του `trader/data/sources/yahoo.py` για OHLCV. Νέος `paper1_RL/yahoo_research_data.py` ως offline-reproducible data layer (bars + earnings + sector + VIX, cached σε npz). Όλη η transformation/signal/gate logic σε **pure functions** (TDD με synthetic fixtures). Το live Yahoo fetch είναι ξεχωριστό "run & verify" βήμα. Τα experiments είναι numpy scripts στο στυλ των υπαρχόντων `all_levers_v3.py` / `ic_analysis.py`.

**Tech Stack:** Python 3.11+, numpy, yfinance 1.4.1, scipy (Wilcoxon), pytest, matplotlib (Agg). No torch.

**Spec:** `docs/superpowers/specs/2026-06-03-der-alpha-signal-engine-design.md`

---

## File Structure

```
paper1_RL/
  universe.py              # ΝΕΟ — fixed ~150 ticker list + sector seed (pure data)
  yahoo_research_data.py   # ΝΕΟ — fetch & cache· pure transforms + live-fetch glue
  signals.py               # ΝΕΟ — pure signal functions (pead_surprise, sector_neutral_mom, vix_theta_scale)
  alpha_gate.py            # ΝΕΟ — γενικευμένο Fundamental-Law gate (από ic_analysis.py)
  pead_experiment.py       # ΝΕΟ — (A) main script
  sector_mom_vol_der.py    # ΝΕΟ — (B) main script
  tests/
    __init__.py            # ΝΕΟ
    conftest.py            # ΝΕΟ — synthetic fixtures (planted-signal & noise universes)
    test_data.py           # ΝΕΟ — earnings matrix, caching
    test_signals.py        # ΝΕΟ — pure signal fns
    test_alpha_gate.py     # ΝΕΟ — gate IC/IR on planted vs noise
  ic_analysis.py           # ΥΠΑΡΧΟΝ — μένει ως-έχει (legacy 2013-2018)· η λογική του μεταφέρεται στο alpha_gate.py
```

**Responsibility split:** `signals.py` = "τι σήμα" (pure, no IO). `alpha_gate.py` = "έχει skill;" (pure, no IO). `yahoo_research_data.py` = "δεδομένα" (IO + pure transforms). Τα `*_experiment.py` = orchestration only.

**Run convention:** όλα τα scripts τρέχουν με cwd = `paper1_RL/` (ίδιο με τα υπάρχοντα, που κάνουν `np.load('close_mat.npy')`). Tests τρέχουν με `python -m pytest paper1_RL/tests/ -v`.

---

## Task 1: Test scaffold + synthetic fixtures

**Files:**
- Create: `paper1_RL/tests/__init__.py`
- Create: `paper1_RL/tests/conftest.py`

- [ ] **Step 1: Create empty package init**

```python
# paper1_RL/tests/__init__.py
```

- [ ] **Step 2: Write synthetic-universe fixtures**

Δύο universes: ένα με **planted signal** (το σήμα προβλέπει την επόμενη απόδοση) και ένα **pure noise**. Seed 2025 (ίδιο με paper). Αυτά είναι το ground truth για όλα τα gate/signal tests.

```python
# paper1_RL/tests/conftest.py
import numpy as np
import pytest

T, N = 600, 60  # μέρες, μετοχές

@pytest.fixture
def rng():
    return np.random.default_rng(2025)

@pytest.fixture
def planted(rng):
    """Universe όπου ενα κρυφο score προβλεπει την επομενη ημερησια αποδοση.
    Επιστρεφει (close, score, fwd) με γνωστο θετικο IC."""
    score = rng.standard_normal((T, N))                  # ο "predictor"
    noise = rng.standard_normal((T, N)) * 0.02
    fwd = 0.01 * score + noise                           # next-day return, IC>0 by construction
    ret = np.zeros((T, N)); ret[1:] = fwd[:-1]           # close-to-close = lagged fwd
    close = 100.0 * np.cumprod(1 + ret, axis=0)
    return dict(close=close, score=score, fwd=fwd)

@pytest.fixture
def noise_only(rng):
    """Universe χωρις σχεση score↔return (IC≈0)."""
    score = rng.standard_normal((T, N))
    ret = rng.standard_normal((T, N)) * 0.02
    close = 100.0 * np.cumprod(1 + ret, axis=0)
    return dict(close=close, score=score)
```

- [ ] **Step 3: Run to verify pytest collects fixtures**

Run: `cd paper1_RL && python -m pytest tests/ -v`
Expected: PASS (0 tests collected, no errors) — ή "no tests ran". Αν δεις collection error, διόρθωσε imports.

- [ ] **Step 4: Commit**

```bash
git add -f paper1_RL/tests/__init__.py paper1_RL/tests/conftest.py
git commit -m "test(paper1_RL): synthetic planted/noise universe fixtures"
```

---

## Task 2: `universe.py` — fixed ticker list

**Files:**
- Create: `paper1_RL/universe.py`
- Test: `paper1_RL/tests/test_data.py`

- [ ] **Step 1: Write failing test**

```python
# paper1_RL/tests/test_data.py
import paper1_RL.universe as U

def test_universe_is_fixed_and_deduped():
    assert 100 <= len(U.TICKERS) <= 200
    assert len(U.TICKERS) == len(set(U.TICKERS))         # no dupes
    assert all(isinstance(t, str) and t.isupper() for t in U.TICKERS)

def test_window_constants():
    assert U.START == "2015-01-01"
    assert U.END == "2024-12-31"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd paper1_RL && python -m pytest tests/test_data.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'paper1_RL.universe'`

> Note: αν το `import paper1_RL.universe` δεν λυθεί, τρέξε τα tests από το repo root `etoro/` με `python -m pytest paper1_RL/tests/ -v` ώστε το `paper1_RL` να είναι package στο path. Πρόσθεσε κενό `paper1_RL/__init__.py` αν λείπει.

- [ ] **Step 3: Write `universe.py`**

~150 liquid large caps (S&P 500 / Nasdaq-100 core). Survivorship bias documented εδώ ρητά.

```python
# paper1_RL/universe.py
"""Fixed research universe. ΠΡΟΣΟΧΗ: current constituents -> survivorship bias
(τεκμηριωμενο limitation στο spec). Window με 2 crashes (2020 COVID, 2022 bear)."""
START = "2015-01-01"
END = "2024-12-31"

TICKERS = [
    "AAPL","MSFT","AMZN","GOOGL","META","NVDA","TSLA","AVGO","ADBE","CRM",
    "ORCL","CSCO","INTC","AMD","QCOM","TXN","INTU","AMAT","MU","ADI",
    "JPM","BAC","WFC","GS","MS","C","AXP","BLK","SCHW","USB",
    "JNJ","UNH","PFE","ABBV","MRK","TMO","ABT","LLY","BMY","AMGN",
    "XOM","CVX","COP","SLB","EOG","PSX","MPC","VLO","OXY","KMI",
    "PG","KO","PEP","COST","WMT","MCD","NKE","SBUX","TGT","LOW",
    "HD","DIS","CMCSA","NFLX","VZ","T","TMUS","CAT","BA","GE",
    "HON","UNP","UPS","RTX","LMT","DE","MMM","EMR","GD","NOC",
    "V","MA","PYPL","FISV","ADP","BKNG","NOW","SNPS","CDNS","KLAC",
    "LRCX","PANW","FTNT","MRVL","CRWD","DDOG","ABNB","UBER","SHOP","SQ",
    "PLD","AMT","CCI","EQIX","SPG","O","PSA","WELL","DLR","AVB",
    "NEE","DUK","SO","D","AEP","EXC","SRE","XEL","PEG","ED",
    "LIN","APD","SHW","ECL","FCX","NEM","DOW","DD","NUE","VMC",
    "GILD","ISRG","REGN","VRTX","MDT","CI","CVS","HUM","ZTS","BDX",
    "MDLZ","CL","KMB","GIS","KHC","SYY","ADM","HSY","STZ","KDP",
]
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd paper1_RL && python -m pytest tests/test_data.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add -f paper1_RL/universe.py paper1_RL/tests/test_data.py
git commit -m "feat(paper1_RL): fixed research universe (~150 large caps, 2015-2024)"
```

---

## Task 3: `yahoo_research_data.py` — earnings-surprise drift matrix (pure)

Η μόνη μη-τετριμμένη transform: μετατρέπει (earnings date, Surprise%) ανά ticker σε ένα `(T,N)` matrix όπου κάθε στήλη κρατά το πιο πρόσφατο surprise για **drift window [+1, +W]** trading days μετά την ανακοίνωση (entry T+1, no look-ahead), αλλιώς `nan`.

**Files:**
- Create: `paper1_RL/yahoo_research_data.py`
- Test: `paper1_RL/tests/test_data.py` (append)

- [ ] **Step 1: Write failing test**

```python
# append to paper1_RL/tests/test_data.py
import numpy as np
import paper1_RL.yahoo_research_data as Y

def test_surprise_matrix_t_plus_1_and_window():
    dates = np.arange(10)                                # 10 trading-day indices
    # ticker 0 ανακοινωνει στο index 2 με surprise +5%· ticker 1 ποτε
    ann = {0: [(2, 5.0)], 1: []}
    W = 3
    M = Y.surprise_matrix(dates, ann, n=2, window=W)
    # entry T+1: index 2 = nan (ημερα ανακοινωσης, δεν ξερουμε ακομα)
    assert np.isnan(M[2, 0])
    # drift window [3,4,5] = 5.0
    assert M[3, 0] == 5.0 and M[4, 0] == 5.0 and M[5, 0] == 5.0
    # εκτος window
    assert np.isnan(M[6, 0])
    # ticker χωρις earnings = ολο nan
    assert np.isnan(M[:, 1]).all()
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd paper1_RL && python -m pytest tests/test_data.py::test_surprise_matrix_t_plus_1_and_window -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'surprise_matrix'`

- [ ] **Step 3: Implement `surprise_matrix` (+ module skeleton)**

```python
# paper1_RL/yahoo_research_data.py
"""Offline-reproducible Yahoo data layer για το signal-engine experiment.
Live fetch -> cache σε npz (μια φορα)· οι transforms ειναι pure & tested."""
from __future__ import annotations
import numpy as np

def surprise_matrix(dates, announcements: dict[int, list[tuple[int, float]]],
                    n: int, window: int = 60) -> np.ndarray:
    """(T,N) matrix· για καθε (ticker j) και drift window [ann+1, ann+window]
    γραφει το Surprise%· entry T+1 (no look-ahead). Default nan.

    announcements[j] = list of (date_index, surprise_pct).
    """
    T = len(dates)
    M = np.full((T, n), np.nan)
    for j, evs in announcements.items():
        for (di, surp) in evs:
            lo, hi = di + 1, min(di + window, T - 1)     # [+1, +window], inclusive
            if lo <= hi:
                M[lo:hi + 1, j] = surp
    return M
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd paper1_RL && python -m pytest tests/test_data.py::test_surprise_matrix_t_plus_1_and_window -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -f paper1_RL/yahoo_research_data.py paper1_RL/tests/test_data.py
git commit -m "feat(paper1_RL): earnings-surprise drift matrix (T+1, no look-ahead)"
```

---

## Task 4: `yahoo_research_data.py` — caching glue + live fetch

Το caching: `load_universe()` φορτώνει από npz αν υπάρχει· αλλιώς fetch & save. Το fetch είναι IO, οπότε το test χρησιμοποιεί monkeypatch (δεν χτυπά δίκτυο).

**Files:**
- Modify: `paper1_RL/yahoo_research_data.py`
- Test: `paper1_RL/tests/test_data.py` (append)

- [ ] **Step 1: Write failing test (cache hit δεν ξανακατεβαζει)**

```python
# append to paper1_RL/tests/test_data.py
def test_load_universe_caches(tmp_path, monkeypatch):
    calls = {"n": 0}
    def fake_fetch():
        calls["n"] += 1
        T, N = 5, 3
        return dict(close=np.ones((T, N)), vol=np.ones((T, N)),
                    dates=np.arange(T), tickers=["A","B","C"],
                    earnings={0: [], 1: [], 2: []},
                    sector={"A":"Tech","B":"Tech","C":"Energy"},
                    vix=np.ones(T))
    monkeypatch.setattr(Y, "_fetch_all", fake_fetch)
    cache = tmp_path / "u.npz"
    d1 = Y.load_universe(cache_path=str(cache))           # miss -> fetch
    d2 = Y.load_universe(cache_path=str(cache))           # hit  -> no fetch
    assert calls["n"] == 1
    assert d2["close"].shape == (5, 3)
    assert list(d2["tickers"]) == ["A","B","C"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd paper1_RL && python -m pytest tests/test_data.py::test_load_universe_caches -v`
Expected: FAIL — `AttributeError: ... '_fetch_all'` / `'load_universe'`

- [ ] **Step 3: Implement caching + live fetch**

```python
# append to paper1_RL/yahoo_research_data.py
import os, sys, warnings, datetime as dt

def _fetch_all() -> dict:
    """LIVE Yahoo pull (μη-ντετερμινιστικο· δεν μπαινει σε unit test).
    Reuse του trader bar-fetcher για OHLCV."""
    import yfinance as yf
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from trader.data.sources.yahoo import fetch_bars
    from datetime import date
    from . import universe as U

    start = date.fromisoformat(U.START); end = date.fromisoformat(U.END)
    # 1) bars -> close/vol matrices σε κοινο date index
    per_ticker = {}
    for tk in U.TICKERS:
        try:
            rows = fetch_bars(tk, start, end, "day")
            per_ticker[tk] = {r["timestamp"]: (r["close"], r["volume"]) for r in rows}
        except Exception as e:
            warnings.warn(f"bars {tk}: {e}")
    all_ts = sorted(set().union(*[set(d) for d in per_ticker.values()]))
    tickers = [t for t in U.TICKERS if t in per_ticker]
    T, N = len(all_ts), len(tickers)
    close = np.full((T, N), np.nan); vol = np.full((T, N), np.nan)
    ts_idx = {ts: i for i, ts in enumerate(all_ts)}
    for j, tk in enumerate(tickers):
        for ts, (c, v) in per_ticker[tk].items():
            close[ts_idx[ts], j] = c; vol[ts_idx[ts], j] = v
    # 2) earnings announcements -> date_index στο all_ts grid
    earnings = {j: [] for j in range(N)}
    for j, tk in enumerate(tickers):
        try:
            ed = yf.Ticker(tk).get_earnings_dates(limit=60)
            if ed is None: continue
            for ts_pd, row in ed.iterrows():
                surp = row.get("Surprise(%)")
                if surp is None or np.isnan(surp): continue
                day_ms = int(dt.datetime(ts_pd.year, ts_pd.month, ts_pd.day,
                             tzinfo=dt.timezone.utc).timestamp() * 1000)
                # nearest trading day <= announcement
                cands = [i for i, ts in enumerate(all_ts) if ts <= day_ms]
                if cands: earnings[j].append((cands[-1], float(surp)))
        except Exception as e:
            warnings.warn(f"earnings {tk}: {e}")
    # 3) sector map
    sector = {}
    for tk in tickers:
        try: sector[tk] = yf.Ticker(tk).info.get("sector", "Unknown")
        except Exception: sector[tk] = "Unknown"
    # 4) VIX aligned στο all_ts
    vix = np.full(T, np.nan)
    try:
        vrows = fetch_bars("^VIX", start, end, "day")
        vmap = {r["timestamp"]: r["close"] for r in vrows}
        for ts, i in ts_idx.items():
            if ts in vmap: vix[i] = vmap[ts]
    except Exception as e:
        warnings.warn(f"vix: {e}")
    return dict(close=close, vol=vol, dates=np.array(all_ts), tickers=tickers,
                earnings=earnings, sector=sector, vix=vix)

def load_universe(cache_path: str = "universe_cache.npz") -> dict:
    """Cache-aside. ΧΩΡΙΣ pickle (security): αριθμητικα arrays -> npz·
    τα dicts/lists (earnings/sector/tickers) -> JSON sidecar. Self-generated
    local cache, αλλα αποφευγουμε allow_pickle εντελως."""
    import json
    side = cache_path + ".json"
    if os.path.exists(cache_path) and os.path.exists(side):
        z = np.load(cache_path)                          # no allow_pickle
        with open(side, encoding="utf-8") as f:
            meta = json.load(f)
        earnings = {int(k): [tuple(ev) for ev in v] for k, v in meta["earnings"].items()}
        return dict(close=z["close"], vol=z["vol"], dates=z["dates"], vix=z["vix"],
                    tickers=meta["tickers"], sector=meta["sector"], earnings=earnings)
    d = _fetch_all()
    np.savez(cache_path, close=d["close"], vol=d["vol"], dates=d["dates"], vix=d["vix"])
    with open(side, "w", encoding="utf-8") as f:
        json.dump(dict(tickers=list(d["tickers"]), sector=d["sector"],
                       earnings={str(k): v for k, v in d["earnings"].items()}), f)
    return d
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd paper1_RL && python -m pytest tests/test_data.py -v`
Expected: PASS (all data tests)

- [ ] **Step 5: Commit**

```bash
git add -f paper1_RL/yahoo_research_data.py paper1_RL/tests/test_data.py
git commit -m "feat(paper1_RL): cache-aside load_universe + live Yahoo fetch glue"
```

---

## Task 5: `signals.py` — pure signal functions

**Files:**
- Create: `paper1_RL/signals.py`
- Test: `paper1_RL/tests/test_signals.py`

- [ ] **Step 1: Write failing tests**

```python
# paper1_RL/tests/test_signals.py
import numpy as np
import paper1_RL.signals as S

def test_zscore_cross_section():
    x = np.array([1.0, 2.0, 3.0])
    z = S.zscore_xs(x)
    assert abs(z.mean()) < 1e-9
    assert abs(z.std() - 1.0) < 1e-6

def test_sector_neutral_demeans_within_group():
    score = np.array([1.0, 3.0, 10.0, 20.0])             # 2 sectors
    sectors = np.array(["A", "A", "B", "B"])
    out = S.sector_neutral(score, sectors)
    # καθε sector εχει mean 0 μετα
    assert abs(out[:2].mean()) < 1e-9
    assert abs(out[2:].mean()) < 1e-9

def test_vix_theta_scale_derisks_when_vix_high():
    w = np.array([1.0, -1.0])
    lo = S.vix_theta_scale(w, vix_now=12.0, vix_ref=20.0)   # ηρεμια -> πιο γεματο
    hi = S.vix_theta_scale(w, vix_now=40.0, vix_ref=20.0)   # stress -> de-risk
    assert np.abs(hi).sum() < np.abs(lo).sum()

def test_pead_signal_uses_surprise_matrix():
    # surprise matrix με 1 ενεργη μερα
    M = np.full((3, 2), np.nan); M[1, 0] = 5.0
    s = S.pead_signal_at(M, t=1)
    assert s[0] == 5.0 and np.isnan(s[1])
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd paper1_RL && python -m pytest tests/test_signals.py -v`
Expected: FAIL — module missing

- [ ] **Step 3: Implement `signals.py`**

```python
# paper1_RL/signals.py
"""Pure signal functions (no IO). Fixed theory-driven signs — ΧΩΡΙΣ learning
(το paper απεδειξε learning -> overfit)."""
from __future__ import annotations
import numpy as np

def zscore_xs(x: np.ndarray) -> np.ndarray:
    """Cross-sectional z-score (ignore nan)."""
    m = np.nanmean(x); s = np.nanstd(x) + 1e-9
    return (x - m) / s

def momentum_12_1(close: np.ndarray, t: int) -> np.ndarray:
    """12-1 momentum (skip last month)."""
    return close[t - 21] / close[t - 252] - 1

def sector_neutral(score: np.ndarray, sectors: np.ndarray) -> np.ndarray:
    """Demean το score ΕΝΤΟΣ καθε sector (εξουδετερωνει sector bet -> momentum crash)."""
    out = score.astype(float).copy()
    for sec in np.unique(sectors):
        mask = sectors == sec
        out[mask] = out[mask] - np.nanmean(out[mask])
    return out

def vix_theta_scale(weights: np.ndarray, vix_now: float, vix_ref: float,
                    lo: float = 0.3, hi: float = 1.5) -> np.ndarray:
    """Practical state-dependent θ: scale exposure ~ vix_ref/vix_now, clipped.
    Υψηλο VIX -> μικροτερο scale -> de-risk."""
    if not np.isfinite(vix_now) or vix_now <= 0:
        return weights
    scale = np.clip(vix_ref / vix_now, lo, hi)
    return weights * scale

def pead_signal_at(surprise_mat: np.ndarray, t: int) -> np.ndarray:
    """Το cross-sectional surprise vector την ημερα t (απο το drift matrix)."""
    return surprise_mat[t]
```

- [ ] **Step 4: Run to verify they pass**

Run: `cd paper1_RL && python -m pytest tests/test_signals.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add -f paper1_RL/signals.py paper1_RL/tests/test_signals.py
git commit -m "feat(paper1_RL): pure signal fns (sector-neutral, vix-theta, pead)"
```

---

## Task 6: `alpha_gate.py` — Fundamental-Law gate (γενίκευση `ic_analysis.py`)

Παίρνει τη λογική του `ic_analysis.py` και τη γενικεύει: δέχεται **signal matrix** `(T,N)` + `close` και επιστρέφει το dict `IC, IC_t, predIR, realIR, TC, ls_ann`. Acceptance: `IC_t > 2`.

**Files:**
- Create: `paper1_RL/alpha_gate.py`
- Test: `paper1_RL/tests/test_alpha_gate.py`

- [ ] **Step 1: Write failing tests (planted -> pass, noise -> fail)**

```python
# paper1_RL/tests/test_alpha_gate.py
import numpy as np
import paper1_RL.alpha_gate as G

def test_gate_detects_planted_signal(planted):
    res = G.evaluate(signal=planted["score"], close=planted["close"], hold=1)
    assert res["IC"] > 0.05
    assert res["IC_t"] > 2          # περναει το gate
    assert G.passes(res)

def test_gate_rejects_noise(noise_only):
    res = G.evaluate(signal=noise_only["score"], close=noise_only["close"], hold=1)
    assert abs(res["IC_t"]) < 2     # κοβεται απο το gate
    assert not G.passes(res)
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd paper1_RL && python -m pytest tests/test_alpha_gate.py -v`
Expected: FAIL — module missing

- [ ] **Step 3: Implement `alpha_gate.py`**

```python
# paper1_RL/alpha_gate.py
"""Fundamental Law of Active Management gate: IR = IC * sqrt(BR) * TC.
Γενικευση του ic_analysis.py — δεχεται αυθαιρετο signal matrix (T,N).
Acceptance: IC_t > 2 (στατιστικα σημαντικο forecasting skill, OOS)."""
from __future__ import annotations
import numpy as np

DELTA = 0.0005  # 5 bps

def _fwd_ret(close, t, hold):
    return close[t + hold] / close[t] - 1

def evaluate(signal: np.ndarray, close: np.ndarray, hold: int = 21,
             oos_frac: float = 0.30) -> dict:
    """signal,(T,N)· OOS μονο. Επιστρεφει IC/IR decomposition + long-short decile."""
    T, N = close.shape
    starts = np.arange(252, T - hold, hold)
    split = int((1 - oos_frac) * len(starts))
    oos = starts[split:]
    ics, ls = [], []
    for t in oos:
        s = signal[t]; f = _fwd_ret(close, t, hold)
        ok = np.isfinite(s) & np.isfinite(f)
        if ok.sum() < 20: continue
        s_, f_ = s[ok], f[ok]
        sd = s_.std()
        if sd < 1e-12: continue
        ics.append(np.corrcoef((s_ - s_.mean()) / sd, f_)[0, 1])
        k = max(3, int(0.1 * len(s_))); o = np.argsort(s_)
        ls.append(f_[o[-k:]].mean() - f_[o[:k]].mean() - 2 * DELTA)
    ic = np.array(ics); ls = np.array(ls)
    if len(ic) == 0:
        return dict(IC=0.0, IC_t=0.0, predIR=0.0, realIR=0.0, TC=0.0, ls_ann=0.0, n=0)
    reb = 252 / hold
    icbar = ic.mean()
    predIR = icbar * np.sqrt(N * reb)
    realIR = ls.mean() / (ls.std() + 1e-9) * np.sqrt(reb)
    return dict(IC=icbar, IC_t=icbar / (ic.std() + 1e-9) * np.sqrt(len(ic)),
                predIR=predIR, realIR=realIR,
                TC=(realIR / predIR if predIR else 0.0),
                ls_ann=ls.mean() * reb, n=len(ic))

def passes(res: dict, t_thresh: float = 2.0) -> bool:
    return abs(res["IC_t"]) > t_thresh
```

- [ ] **Step 4: Run to verify they pass**

Run: `cd paper1_RL && python -m pytest tests/test_alpha_gate.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Run full suite + commit**

Run: `cd paper1_RL && python -m pytest tests/ -v`
Expected: PASS (all)

```bash
git add -f paper1_RL/alpha_gate.py paper1_RL/tests/test_alpha_gate.py
git commit -m "feat(paper1_RL): generalized Fundamental-Law alpha gate"
```

---

## Task 7: Data pull (run & verify — μη unit-testable)

Live Yahoo pull μία φορά → cache. Verify shapes/sanity, **όχι** unit test.

**Files:**
- Create: `paper1_RL/universe_cache.npz` + `paper1_RL/universe_cache.npz.json` (artifacts — git-ignored)

- [ ] **Step 1: Pull & cache**

Run: `cd paper1_RL && python -c "import yahoo_research_data as Y; d=Y.load_universe(); print('close', d['close'].shape, 'tickers', len(d['tickers']), 'vix finite', __import__('numpy').isfinite(d['vix']).sum())"`
Expected: `close (~2500, ~140)`, tickers ~130-150, vix finite > 2000. (Διάρκεια: λεπτά — rate limits.)

- [ ] **Step 2: Sanity-verify earnings coverage**

Run: `cd paper1_RL && python -c "import yahoo_research_data as Y; d=Y.load_universe(); e=d['earnings']; tot=sum(len(v) for v in e.values()); print('earnings events', tot, '| stocks με >=10 events', sum(len(v)>=10 for v in e.values()))"`
Expected: earnings events > 2000· τα περισσότερα stocks με ≥10 events (≥40 τρίμηνα ιστορικό όπου διαθέσιμα).

- [ ] **Step 3: Commit the data note (όχι το npz αν είναι μεγάλο)**

```bash
printf "universe_cache.npz\nuniverse_cache.npz.json\n" >> ../.gitignore
git add ../.gitignore
git commit -m "chore(paper1_RL): gitignore universe data cache artifacts"
```

> Αν το pull αποτύχει λόγω rate-limit/network, ξανατρέξε — το cache-aside κρατά ό,τι κατέβηκε. Κατάγραψε στο write-up πόσα tickers/events τελικά καλύφθηκαν.

---

## Task 8: (A) `pead_experiment.py` — PEAD directional alpha

**Files:**
- Create: `paper1_RL/pead_experiment.py`

- [ ] **Step 1: Write the script (orchestration only — building blocks ήδη tested)**

```python
# paper1_RL/pead_experiment.py
"""(A) PEAD / earnings-surprise drift. Gate -> long-short + DER overlay.
Building blocks: yahoo_research_data, signals, alpha_gate (ολα tested)."""
import numpy as np
import yahoo_research_data as Y
import signals as S
from alpha_gate import evaluate, passes

WINDOW = 60   # drift window σε trading days

def build_surprise_signal(d):
    close = d["close"]; T, N = close.shape
    earn = d["earnings"]                                 # {int: [(date_idx, surp), ...]}
    M = Y.surprise_matrix(np.arange(T), earn, n=N, window=WINDOW)
    # cross-sectional z-score ανα μερα (relative surprise)
    Z = np.full_like(M, np.nan)
    for t in range(T):
        if np.isfinite(M[t]).sum() >= 5:
            Z[t] = S.zscore_xs(M[t])
    return Z

def main():
    d = Y.load_universe()
    close = d["close"]; vix = d["vix"]
    Z = build_surprise_signal(d)

    res = evaluate(signal=Z, close=close, hold=21)
    print("=== (A) PEAD surprise — Fundamental-Law gate (OOS) ===")
    print(f"IC={res['IC']:.4f}  t={res['IC_t']:.2f}  predIR={res['predIR']:.2f}  "
          f"realIR={res['realIR']:.2f}  TC={res['TC']:.2f}  n={res['n']}")
    if not passes(res):
        print(">> ΑΠΟΡΡΙΨΗ: IC_t<=2 — κανενα alpha claim (τιμια αναφορα).")
        return
    print(">> PASS: στατιστικα σημαντικο σημα -> strategy backtest.")

    # long-short market-neutral με DER vol-target (VIX-driven θ) overlay
    T, N = close.shape
    ret = np.zeros_like(close); ret[1:] = close[1:] / close[:-1] - 1
    vix_ref = np.nanmedian(vix[:int(0.7*T)])
    Rs = []
    days = np.arange(252, T - 1)
    split = int(0.7 * len(days))
    for t in days[split:]:
        s = Z[t]
        if np.isfinite(s).sum() < 10: Rs.append(0.0); continue
        w = np.nan_to_num(s); w = w / (np.nansum(np.abs(w)) + 1e-9)   # mkt-neutral, gross 1
        w = S.vix_theta_scale(w, vix[t], vix_ref)
        Rs.append(np.nansum(w * ret[t + 1]) - 0.0005 * np.nansum(np.abs(w)))
    R = np.array(Rs); eq = np.cumprod(1 + R)
    dn = R[R < 0]
    print(f"Strategy OOS: ret={eq[-1]-1:.1%}  Sharpe={R.mean()/(R.std()+1e-9)*np.sqrt(252):.2f}"
          f"  Sortino={R.mean()/(dn.std()+1e-9)*np.sqrt(252):.2f}"
          f"  MaxDD={np.min(eq/np.maximum.accumulate(eq)-1):.1%}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it**

Run: `cd paper1_RL && python pead_experiment.py`
Expected: τυπώνει το gate decomposition. Είτε PASS+metrics είτε «ΑΠΟΡΡΙΨΗ» — **και τα δύο είναι valid αποτελέσματα** (το paper τιμά την απόρριψη). Καμία εξαίρεση/crash.

- [ ] **Step 3: Commit**

```bash
git add -f paper1_RL/pead_experiment.py
git commit -m "feat(paper1_RL): (A) PEAD earnings-surprise experiment with alpha gate"
```

---

## Task 9: (B) `sector_mom_vol_der.py` — sector-neutral momentum + VIX-θ

**Files:**
- Create: `paper1_RL/sector_mom_vol_der.py`

- [ ] **Step 1: Write the script**

```python
# paper1_RL/sector_mom_vol_der.py
"""(B) Sector-neutral 12-1 momentum + VIX-driven θ (state-dependent DER risk).
Compare: plain mom -> sector-neutral -> sector-neutral + VIX-θ. Walk-forward OOS.
Report stand-alone ΚΑΙ combined-with-market (paper §sec:future roadmap #3)."""
import numpy as np
import yahoo_research_data as Y
import signals as S
from alpha_gate import evaluate, passes
from scipy.stats import wilcoxon

def metrics(R, p=252):
    R = np.asarray(R); eq = np.cumprod(1 + R); dn = R[R < 0]
    return dict(ret=eq[-1]-1, sh=R.mean()/(R.std()+1e-9)*np.sqrt(p),
                so=(R.mean()/(dn.std()+1e-9)*np.sqrt(p)) if len(dn) > 1 else np.nan,
                mdd=np.min(eq/np.maximum.accumulate(eq)-1), eq=eq, R=R)

def main():
    d = Y.load_universe()
    close = d["close"]; vix = d["vix"]
    sec_map = d["sector"]                                # {ticker: sector}
    tickers = list(d["tickers"])
    sectors = np.array([sec_map.get(t, "Unknown") for t in tickers])
    T, N = close.shape
    ret = np.zeros_like(close); ret[1:] = close[1:] / close[:-1] - 1

    # build daily momentum + sector-neutral momentum signal matrices
    mom = np.full((T, N), np.nan); smom = np.full((T, N), np.nan)
    for t in range(252, T):
        m = S.momentum_12_1(close, t)
        mom[t] = S.zscore_xs(m)
        smom[t] = S.zscore_xs(S.sector_neutral(np.nan_to_num(m), sectors))

    # gate και για τα δυο
    for name, sig in [("plain 12-1 mom", mom), ("sector-neutral mom", smom)]:
        r = evaluate(signal=sig, close=close, hold=21)
        tag = "PASS" if passes(r) else "reject"
        print(f"[gate] {name:<22} IC={r['IC']:.4f} t={r['IC_t']:.2f} "
              f"realIR={r['realIR']:.2f} -> {tag}")

    # walk-forward portfolios
    days = np.arange(252, T - 1); split = int(0.7 * len(days)); te = days[split:]
    vix_ref = np.nanmedian(vix[:days[split]])
    def port(sig, use_vix):
        Rs = []
        for t in te:
            s = sig[t]
            if np.isfinite(s).sum() < 10: Rs.append(0.0); continue
            w = np.nan_to_num(s); w = w / (np.nansum(np.abs(w)) + 1e-9)
            if use_vix: w = S.vix_theta_scale(w, vix[t], vix_ref)
            Rs.append(np.nansum(w * ret[t+1]) - 0.0005 * np.nansum(np.abs(w)))
        return np.array(Rs)

    mkt = np.array([np.nanmean(ret[t+1]) for t in te])
    res = {
        "Market (long-only)":        metrics(mkt),
        "Plain mom":                 metrics(port(mom, False)),
        "Sector-neutral mom":        metrics(port(smom, False)),
        "Sector-neutral + VIX-θ":    metrics(port(smom, True)),
    }
    R_ov = res["Sector-neutral + VIX-θ"]["R"]; L = min(len(mkt), len(R_ov))
    res["Market + overlay"] = metrics(0.7*mkt[:L] + 0.5*R_ov[:L])

    print(f"\n{'Strategy':<26}{'Return':>9}{'Sharpe':>9}{'Sortino':>9}{'MaxDD':>9}")
    print("-"*62)
    for k, m in res.items():
        print(f"{k:<26}{m['ret']*100:>8.1f}%{m['sh']:>9.2f}{m['so']:>9.2f}{m['mdd']*100:>8.1f}%")

    # stressed sub-periods (2020 COVID & 2022 bear): τελευταιο 1/3 του test ως proxy
    print("\nStressed check (worst 60-day MaxDD στο OOS):")
    for k in ["Market (long-only)", "Sector-neutral + VIX-θ"]:
        R = res[k]["R"]
        worst = min(np.min(np.cumprod(1+R[i:i+60])/np.maximum.accumulate(np.cumprod(1+R[i:i+60]))-1)
                    for i in range(0, max(1, len(R)-60), 10))
        print(f"  {k:<26}{worst*100:>8.1f}%")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it**

Run: `cd paper1_RL && python sector_mom_vol_der.py`
Expected: gate γραμμές + στρατηγικός πίνακας + stressed check. Καμία εξαίρεση. Αναμένουμε sector-neutral να βελτιώνει MaxDD vs plain mom· VIX-θ να μειώνει το stressed MaxDD.

- [ ] **Step 3: Commit**

```bash
git add -f paper1_RL/sector_mom_vol_der.py
git commit -m "feat(paper1_RL): (B) sector-neutral momentum + VIX-driven theta"
```

---

## Task 10: (C) Write-up handoff

**Files:**
- Modify: `paper1_RL/der_paper_full.tex` (§`sec:alpha` extension) — μέσω academic-paper-writer

- [ ] **Step 1: Συγκέντρωσε τα αποτελέσματα**

Τρέξε ξανά (A) και (B), κράτα: τις γραμμές gate (IC, t, predIR, realIR, TC) για PEAD & sector-neutral mom· τους στρατηγικούς πίνακες· το stressed check. Αυτά γίνονται **νέες γραμμές στον `tab:ic`** + ένα νέο walk-forward παράγραφο/πίνακα.

- [ ] **Step 2: Invoke academic-paper-writer**

Κάλεσε το `academic-paper-writer` skill με στόχο: «extend §sec:alpha του `der_paper_full.tex` με (i) νέες γραμμές `tab:ic` για PEAD surprise + sector-neutral momentum σε Yahoo 2015-2024, (ii) walk-forward + stressed (2020/2022) validation, (iii) ρητή καταγραφή survivorship & estimate-revision limitations». Το skill χειρίζεται LaTeX/proofs/references.

- [ ] **Step 3: Commit (από το skill)**

```bash
git add -f paper1_RL/der_paper_full.tex
git commit -m "docs(paper1_RL): extend sec:alpha with Yahoo 2015-2024 signal-engine validation"
```

---

## Self-Review notes

- **Spec coverage:** data layer (T2-4,7), gate (T6), (A) PEAD (T3,5,8), (B) sector-neutral+VIX-θ (T5,9), combined+stressed (T9), (C) write-up (T10), no-learning/fixed-signs (signals.py docstring + design), survivorship documented (universe.py + T10). ✓
- **No production scope** — confirmed out (spec non-goal). ✓
- **Type consistency:** `evaluate()`/`passes()` signatures identical across T6/T8/T9· `load_universe()` dict keys (close/vol/dates/tickers/earnings/sector/vix) identical across tasks· `surprise_matrix(dates, announcements, n, window)` identical T3/T8. ✓
- **Honest-result handling:** T8/T9 treat gate rejection as a valid published outcome (no crash, explicit print) — consistent με το ύφος του paper. ✓
