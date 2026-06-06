# paper4 — Changepoint-Aware Momentum Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a changepoint-aware time-series momentum strategy whose trend signal and "fast reversion" gate both come from a single Kalman local-linear-trend belief, evaluated by an honest cost-aware walk-forward, producing the first real-data IR/DSR/durability numbers.

**Architecture:** Pure-numpy math units (Kalman LLT filter, BOCPD detector, signal builders) under `Strategies/slow-momentum-fast-reversion/`, plus a walk-forward harness (cost model + metrics + runner) under `paper4/code/`. Three strategy variants (`tsmom`, `cpd_momentum`, `belief_gated`) share one backtest path for an apples-to-apples ablation. Data is Yahoo daily for an as-traded S&P 100 universe.

**Tech Stack:** Python 3.11+, numpy, pandas, pytest, yfinance (via `trader.data.sources.yahoo`), matplotlib (figures only).

**Spec:** `docs/superpowers/specs/2026-06-06-paper4-changepoint-momentum-design.md`

---

## File structure

```
Strategies/slow-momentum-fast-reversion/
  __init__.py
  kalman_llt.py     # LLT Kalman filter -> level, velocity, trend_sig, std_innov
  bocpd.py          # Bayesian online changepoint detection -> break severity
  signals.py        # momentum primitives + 3 weight builders (tsmom/cpd/belief_gated)
  README.md
  tests/
    __init__.py
    test_kalman_llt.py
    test_bocpd.py
    test_signals.py
paper4/
  code/               # NOT a Python package — the name 'code' shadows the stdlib `code`
                      # module and breaks pytest's package import. No __init__.py here; all
                      # modules are top-level, resolved via cwd when run from this dir.
    universe.py     # frozen as-traded S&P 100 list + START/END
    data.py         # cache-aside (T,N) close matrix from Yahoo (npz)
    costs.py        # spread + turnover + short-financing
    metrics.py      # IR, max_dd, Newey-West t, deflated Sharpe, durability
    harness.py      # walk-forward runner wiring everything
    run_paper4.py   # CLI entry: produces tables + figures
    tests/          # NO __init__.py (same reason); run from `cd paper4/code`
      test_costs.py
      test_metrics.py
      test_harness.py
  figures/
  paper_skeleton.tex
```

Run tests with:
`cd Strategies/slow-momentum-fast-reversion && python -m pytest tests -q`  (strategy units)
`cd paper4/code && python -m pytest tests -q`  (engine units — must run from this dir)

---

## Task 1: Scaffolding (packages + universe)

**Files:**
- Create: `Strategies/slow-momentum-fast-reversion/__init__.py` (empty)
- Create: `Strategies/slow-momentum-fast-reversion/tests/__init__.py` (empty)
- Create: `paper4/code/universe.py`

> **Do NOT create `__init__.py` under `paper4/code/`.** The directory name `code` shadows
> Python's stdlib `code` module; with an `__init__.py` present pytest tries to import a
> package named `code` and collection fails (`'code' is not a package`). Leave `paper4/code`
> and `paper4/code/tests` as plain directories; their modules run as top-level (resolved via
> cwd) when invoked from `cd paper4/code`. Only the strategy package gets `__init__.py`
> (its hyphenated name can't form a package path, so it's immune to the clash).

- [ ] **Step 1: Create the two strategy `__init__.py` files** (empty).

- [ ] **Step 2: Write `paper4/code/universe.py`** — frozen S&P 100 (as-traded snapshot; survivorship caveat documented in spec §5):

```python
# paper4/code/universe.py
"""Frozen S&P 100 universe for paper4. Snapshot list; survivorship caveat in spec."""
START = "2000-01-01"
END = "2024-12-31"

TICKERS = [
    "AAPL","ABBV","ABT","ACN","ADBE","AIG","AMD","AMGN","AMT","AMZN",
    "AVGO","AXP","BA","BAC","BK","BKNG","BLK","BMY","C","CAT",
    "CHTR","CL","CMCSA","COF","COP","COST","CRM","CSCO","CVS","CVX",
    "DHR","DIS","DOW","DUK","EMR","FDX","GD","GE","GILD","GM",
    "GOOGL","GS","HD","HON","IBM","INTC","JNJ","JPM","KO","LIN",
    "LLY","LMT","LOW","MA","MCD","MDT","MET","META","MMM","MO",
    "MRK","MS","MSFT","NEE","NFLX","NKE","NVDA","ORCL","PEP","PFE",
    "PG","PM","PYPL","QCOM","RTX","SBUX","SO","SPG","T","TGT",
    "TMO","TMUS","TSLA","TXN","UNH","UNP","UPS","USB","V","VZ",
    "WFC","WMT","XOM",
]
```

- [ ] **Step 3: Commit**

```bash
git add Strategies/slow-momentum-fast-reversion paper4/code/__init__.py paper4/code/tests/__init__.py paper4/code/universe.py
git commit -m "feat(paper4): scaffold packages + frozen S&P 100 universe"
```

---

## Task 2: Kalman LLT filter

**Files:**
- Create: `Strategies/slow-momentum-fast-reversion/kalman_llt.py`
- Test: `Strategies/slow-momentum-fast-reversion/tests/test_kalman_llt.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_kalman_llt.py
import numpy as np
from kalman_llt import kalman_llt   # run pytest from the package dir, or use full path import

def test_recovers_linear_trend():
    t = np.arange(400)
    b = 0.01
    rng = np.random.default_rng(0)
    y = 5.0 + b * t + rng.normal(0, 1e-3, 400)
    out = kalman_llt(y, q_level=1e-5, q_vel=1e-7, r_obs=1e-6)
    assert abs(np.mean(out["velocity"][-50:]) - b) < 2e-3

def test_innovation_spikes_at_level_break():
    rng = np.random.default_rng(1)
    y = np.concatenate([np.zeros(150), np.full(150, 0.5)]) + rng.normal(0, 1e-3, 300)
    out = kalman_llt(y, q_level=1e-5, q_vel=1e-7, r_obs=1e-6)
    si = np.abs(out["std_innov"])
    assert si[150] > 5.0
    assert si[150] >= si[50:140].max()

def test_output_keys_and_length():
    out = kalman_llt(np.linspace(0, 1, 50))
    for k in ("level","velocity","vel_var","innovation","innov_var","trend_sig","std_innov"):
        assert out[k].shape == (50,)
```

- [ ] **Step 2: Run, verify FAIL** — `python -m pytest Strategies/slow-momentum-fast-reversion/tests/test_kalman_llt.py -q` → ImportError / fail.

- [ ] **Step 3: Implement**

```python
# Strategies/slow-momentum-fast-reversion/kalman_llt.py
"""Local-linear-trend Kalman filter (pure numpy, no IO).
State x=[level, velocity]; F=[[1,1],[0,1]], H=[1,0]. Returns belief read-offs:
filtered level, trend velocity, trend significance (t-stat), standardized innovation."""
from __future__ import annotations
import numpy as np


def kalman_llt(log_price, q_level=1e-5, q_vel=1e-7, r_obs=1e-6, init_var=1.0):
    y = np.asarray(log_price, dtype=float)
    T = len(y)
    F = np.array([[1.0, 1.0], [0.0, 1.0]])
    H = np.array([[1.0, 0.0]])
    Q = np.array([[q_level, 0.0], [0.0, q_vel]])
    x = np.array([[y[0]], [0.0]])
    P = np.eye(2) * init_var

    level = np.empty(T); vel = np.empty(T); vel_var = np.empty(T)
    innov = np.empty(T); innov_var = np.empty(T)
    for t in range(T):
        x = F @ x                       # predict state
        P = F @ P @ F.T + Q             # predict covariance
        nu = y[t] - (H @ x)[0, 0]       # innovation
        S = (H @ P @ H.T)[0, 0] + r_obs
        K = (P @ H.T) / S               # 2x1 gain
        x = x + K * nu                  # update state
        P = (np.eye(2) - K @ H) @ P     # update covariance
        level[t] = x[0, 0]; vel[t] = x[1, 0]; vel_var[t] = P[1, 1]
        innov[t] = nu; innov_var[t] = S

    return {
        "level": level, "velocity": vel, "vel_var": vel_var,
        "innovation": innov, "innov_var": innov_var,
        "trend_sig": vel / np.sqrt(vel_var + 1e-12),
        "std_innov": innov / np.sqrt(innov_var + 1e-12),
    }
```

- [ ] **Step 4: Run, verify PASS** — same pytest command → 3 passed.

- [ ] **Step 5: Commit**

```bash
git add Strategies/slow-momentum-fast-reversion/kalman_llt.py Strategies/slow-momentum-fast-reversion/tests/test_kalman_llt.py
git commit -m "feat(paper4): Kalman LLT filter with trend + innovation read-offs"
```

---

## Task 3: BOCPD changepoint detector

**Files:**
- Create: `Strategies/slow-momentum-fast-reversion/bocpd.py`
- Test: `Strategies/slow-momentum-fast-reversion/tests/test_bocpd.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_bocpd.py
import numpy as np
from bocpd import bocpd_gaussian

def test_detects_mean_shift():
    rng = np.random.default_rng(0)
    x = np.concatenate([rng.normal(0, 1, 150), rng.normal(4, 1, 150)])
    sev = bocpd_gaussian(x, hazard=1/100, sigma2=1.0)
    assert sev[150:165].max() > 0.3        # spikes shortly after the shift
    assert sev[40:140].max() < 0.25        # quiet in the stable segment

def test_quiet_on_stationary():
    rng = np.random.default_rng(1)
    x = rng.normal(0, 1, 400)
    sev = bocpd_gaussian(x, hazard=1/250, sigma2=1.0)
    assert sev.mean() < 0.1

def test_severity_in_unit_interval_and_length():
    sev = bocpd_gaussian(np.zeros(30), hazard=1/50, sigma2=1.0)
    assert sev.shape == (30,)
    assert (sev >= 0).all() and (sev <= 1).all()
```

- [ ] **Step 2: Run, verify FAIL.**

- [ ] **Step 3: Implement**

```python
# Strategies/slow-momentum-fast-reversion/bocpd.py
"""Bayesian Online Changepoint Detection (Adams & MacKay 2007), constant hazard,
Gaussian predictive with a Normal-Normal conjugate prior on the run mean and a
fixed observation variance sigma2. Returns per-step break severity = posterior
mass on short run lengths P(r_t < kshort) — this rises sharply after a regime break
(the run-length mass collapses to small r). NOTE: the normalized P(r_t = 0) is NOT a
usable detector — it equals the hazard at every step by construction; the collapse of
mass onto short run lengths is what carries the changepoint signal."""
from __future__ import annotations
import numpy as np


def bocpd_gaussian(x, hazard=1/250.0, mu0=0.0, kappa0=1.0, sigma2=1.0, rmax=300, kshort=5):
    x = np.asarray(x, dtype=float)
    T = len(x)
    R = np.zeros(rmax + 1); R[0] = 1.0       # run-length posterior
    sums = np.zeros(rmax + 1)                 # sum of obs in each run
    counts = np.zeros(rmax + 1)               # count of obs in each run
    severity = np.zeros(T)

    for t in range(T):
        post_prec = 1.0 / kappa0 + counts / sigma2
        post_mean = (mu0 / kappa0 + sums / sigma2) / post_prec
        pred_var = sigma2 + 1.0 / post_prec
        pred = np.exp(-0.5 * (x[t] - post_mean) ** 2 / pred_var) / np.sqrt(2 * np.pi * pred_var)

        growth = R * pred * (1.0 - hazard)
        cp = np.sum(R * pred * hazard)
        newR = np.zeros(rmax + 1)
        newR[1:] = growth[:-1]
        newR[0] = cp
        newR /= (newR.sum() + 1e-300)
        R = newR
        severity[t] = R[:kshort].sum()       # mass on short run lengths = break severity

        new_sums = np.zeros(rmax + 1); new_counts = np.zeros(rmax + 1)
        new_sums[1:] = sums[:-1] + x[t]
        new_counts[1:] = counts[:-1] + 1.0
        sums, counts = new_sums, new_counts

    return severity
```

- [ ] **Step 4: Run, verify PASS.**

- [ ] **Step 5: Commit**

```bash
git add Strategies/slow-momentum-fast-reversion/bocpd.py Strategies/slow-momentum-fast-reversion/tests/test_bocpd.py
git commit -m "feat(paper4): BOCPD changepoint detector (break severity)"
```

---

## Task 4: Signal builders (tsmom / cpd_momentum / belief_gated)

**Files:**
- Create: `Strategies/slow-momentum-fast-reversion/signals.py`
- Test: `Strategies/slow-momentum-fast-reversion/tests/test_signals.py`

Interface: all builders take matrices and return a `(T, N)` weight matrix, dollar-neutral
(`sum |w| ` per row = 1 when active, `sum w ≈ 0`), zero before warmup. `vel`, `trend_sig`,
`sev` are per-asset matrices precomputed by applying Task 2/3 column-wise (done in harness).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_signals.py
import numpy as np
from signals import zscore_xs, xs_weights, build_weights, momentum_matrix

def test_xs_weights_dollar_neutral():
    score = np.array([3.0, 1.0, -1.0, -3.0, np.nan])
    w = xs_weights(score, k=1)
    assert np.isclose(np.nansum(w), 0.0)
    assert np.isclose(np.nansum(np.abs(w)), 1.0)
    assert w[0] > 0 and w[3] < 0           # top long, bottom short

def test_xs_weights_too_few_valid_returns_zero():
    w = xs_weights(np.array([1.0, np.nan, np.nan]), k=2)
    assert np.allclose(w, 0.0)

def test_momentum_matrix_shape_and_warmup():
    close = np.cumprod(1 + np.zeros((300, 5)) + 0.001, axis=0) * 100
    M = momentum_matrix(close, lookback=252, skip=21)
    assert M.shape == (300, 5)
    assert np.isnan(M[100]).all()          # before warmup -> nan
    assert np.isfinite(M[260]).all()

def test_build_weights_variants_run():
    T, N = 300, 6
    rng = np.random.default_rng(0)
    close = np.cumprod(1 + rng.normal(0.0003, 0.01, (T, N)), axis=0) * 100
    vel = rng.normal(0, 1e-3, (T, N))
    sig = rng.normal(0, 1, (T, N))
    sev = np.abs(rng.normal(0, 0.1, (T, N))).clip(0, 1)
    for variant in ("tsmom", "cpd_momentum", "belief_gated"):
        W = build_weights(variant, close, vel, sig, sev, k=2, warmup=252)
        assert W.shape == (T, N)
        assert np.allclose(W[:252], 0.0)            # warmup zeroed
        row = W[260]
        assert abs(np.nansum(row)) < 1e-9           # dollar neutral
        assert np.nansum(np.abs(row)) <= 1.0 + 1e-9 # gating never grosses up

def test_belief_gated_trades_only_significant_names():
    # belief_gated must EXCLUDE statistically-insignificant trends (composition changes IR,
    # unlike a magnitude scale which xs_weights normalizes away).
    T, N = 300, 20
    rng = np.random.default_rng(1)
    close = np.cumprod(1 + rng.normal(0.0003, 0.01, (T, N)), axis=0) * 100
    vel = rng.normal(0, 1e-3, (T, N))
    sev = np.zeros((T, N))
    sig = np.zeros((T, N)); sig[:, :10] = 5.0; sig[:, 10:] = 0.1   # first 10 significant
    W = build_weights("belief_gated", close, vel, sig, sev, k=3, warmup=252, sig_thresh=1.0)
    row = W[260]
    assert np.allclose(row[10:], 0.0)               # insignificant names never traded
    assert np.nansum(np.abs(row)) > 0               # significant names do trade
```

- [ ] **Step 2: Run, verify FAIL.**

- [ ] **Step 3: Implement**

```python
# Strategies/slow-momentum-fast-reversion/signals.py
"""Momentum primitives + three weight builders sharing one cross-sectional constructor.
All builders return (T,N) dollar-neutral weight matrices, zeroed during warmup."""
from __future__ import annotations
import numpy as np


def zscore_xs(x):
    m = np.nanmean(x); s = np.nanstd(x) + 1e-9
    return (x - m) / s


def xs_weights(score, k):
    """Long top-k, short bottom-k, equal weight, dollar-neutral, gross=1."""
    w = np.zeros(len(score), dtype=float)
    valid = np.where(np.isfinite(score))[0]
    if len(valid) < 2 * k:
        return w
    order = valid[np.argsort(score[valid])]
    w[order[-k:]] = 0.5 / k
    w[order[:k]] = -0.5 / k
    return w


def momentum_matrix(close, lookback=252, skip=21):
    """(T,N) classic 12-1 momentum: close[t-skip]/close[t-lookback]-1, nan before warmup."""
    T, N = close.shape
    M = np.full((T, N), np.nan)
    for t in range(lookback, T):
        M[t] = close[t - skip] / close[t - lookback] - 1.0
    return M


def build_weights(variant, close, vel, trend_sig, sev, k, warmup=252,
                  sig_thresh=1.0, sev_floor=0.2):
    """Return (T,N) weights for one of: tsmom | cpd_momentum | belief_gated.

    tsmom        : score = 12-1 momentum; full gross.
    cpd_momentum : score = Kalman velocity; gross scaled by time-varying (1 - severity).
    belief_gated : velocity ranking, but ONLY among names whose trend is statistically
                   significant (|trend_sig| >= sig_thresh); time-varying severity gross gate.
                   Significance changes WHICH names trade (book composition), so it moves IR
                   — a magnitude multiplier would not, since xs_weights is rank-based and
                   normalizes magnitude away. This is what distinguishes it from cpd_momentum.
    """
    T, N = close.shape
    W = np.zeros((T, N))
    mom = momentum_matrix(close, lookback=warmup, skip=21) if variant == "tsmom" else None
    for t in range(warmup, T):
        if variant == "tsmom":
            score = zscore_xs(mom[t])
            gate = 1.0
        elif variant == "cpd_momentum":
            score = zscore_xs(vel[t])
            gate = 1.0 - np.nanmean(sev[t])
        elif variant == "belief_gated":
            score = zscore_xs(vel[t])
            score[np.abs(trend_sig[t]) < sig_thresh] = np.nan   # drop insignificant trends
            gate = 1.0 - np.nanmean(sev[t])
        else:
            raise ValueError(f"unknown variant {variant!r}")
        gate = max(gate, sev_floor)         # never fully flat; keep some exposure
        W[t] = xs_weights(score, k) * gate
    return W
```

- [ ] **Step 4: Run, verify PASS.**

- [ ] **Step 5: Commit**

```bash
git add Strategies/slow-momentum-fast-reversion/signals.py Strategies/slow-momentum-fast-reversion/tests/test_signals.py
git commit -m "feat(paper4): signal builders (tsmom/cpd_momentum/belief_gated)"
```

---

## Task 5: Cost model

**Files:**
- Create: `paper4/code/costs.py`
- Test: `paper4/code/tests/test_costs.py`

- [ ] **Step 1: Write the failing tests**

```python
# paper4/code/tests/test_costs.py
import numpy as np
from costs import net_returns

def test_no_turnover_no_short_equals_gross():
    w = np.array([[0.5, 0.5], [0.5, 0.5]])
    fwd = np.array([[0.01, 0.02], [0.0, 0.0]])
    net = net_returns(w, fwd, spread_bps=10.0, short_fin_bps_annual=300.0)
    # row 0 charges initial turnover (1.0); row 1 has no turnover, no shorts
    assert np.isclose(net[1], 0.0)

def test_short_financing_charged():
    w = np.array([[0.5, -0.5]])
    fwd = np.array([[0.0, 0.0]])
    net = net_returns(w, fwd, spread_bps=0.0, short_fin_bps_annual=2520.0)  # 0.01/day on 1bp basis
    # short notional 0.5 -> daily fin = (2520/1e4/252)*0.5 = 0.001*0.5 = 5e-4
    assert np.isclose(net[0], -5e-4)

def test_turnover_charged_on_rebalance():
    w = np.array([[0.0, 0.0], [1.0, -1.0]])
    fwd = np.array([[0.0, 0.0], [0.0, 0.0]])
    net = net_returns(w, fwd, spread_bps=10.0, short_fin_bps_annual=0.0)
    # row1 turnover = |1-0|+|-1-0| = 2.0 ; cost = 10/1e4 * 2 = 0.002
    assert np.isclose(net[1], -0.002)
```

- [ ] **Step 2: Run, verify FAIL.**

- [ ] **Step 3: Implement**

```python
# paper4/code/costs.py
"""Realistic cost model: bid/ask spread on turnover + overnight short financing
(eToro CFD reality). Inputs are aligned (M,N) weight and next-day return matrices."""
from __future__ import annotations
import numpy as np


def net_returns(weights, fwd_ret, spread_bps=5.0, short_fin_bps_annual=300.0):
    weights = np.asarray(weights, float)
    fwd_ret = np.asarray(fwd_ret, float)
    gross = np.nansum(weights * fwd_ret, axis=1)

    turn = np.empty(len(weights))
    turn[0] = np.nansum(np.abs(weights[0]))
    if len(weights) > 1:
        turn[1:] = np.nansum(np.abs(weights[1:] - weights[:-1]), axis=1)
    tc = (spread_bps / 1e4) * turn

    short_notional = np.nansum(np.clip(-weights, 0.0, None), axis=1)
    fin = (short_fin_bps_annual / 1e4 / 252.0) * short_notional
    return gross - tc - fin
```

- [ ] **Step 4: Run, verify PASS.**

- [ ] **Step 5: Commit**

```bash
git add paper4/code/costs.py paper4/code/tests/test_costs.py
git commit -m "feat(paper4): cost model (spread turnover + short financing)"
```

---

## Task 6: Metrics (IR, max DD, Newey-West t, Deflated Sharpe, durability)

**Files:**
- Create: `paper4/code/metrics.py`
- Test: `paper4/code/tests/test_metrics.py`

- [ ] **Step 1: Write the failing tests**

```python
# paper4/code/tests/test_metrics.py
import numpy as np
from metrics import ann_ir, max_drawdown, newey_west_t, deflated_sharpe, durability_by_year

def test_ann_ir_positive_drift():
    rng = np.random.default_rng(0)
    r = rng.normal(0.0005, 0.01, 2520)     # ~0.8 Sharpe-ish
    assert ann_ir(r) > 0.3

def test_max_drawdown_known():
    r = np.array([0.1, -0.5, 0.0])         # equity 1.1 -> 0.55 -> 0.55
    dd = max_drawdown(r)
    assert dd < -0.45 and dd > -0.55

def test_newey_west_t_zero_mean_small():
    rng = np.random.default_rng(4)              # stable seed: zero-mean -> |t| ~ 0.3
    r = rng.normal(0.0, 0.01, 2000)
    assert abs(newey_west_t(r, lag=21)) < 2.5

def test_deflated_sharpe_penalizes_trials():
    rng = np.random.default_rng(3)
    r = rng.normal(0.0008, 0.01, 2520)
    dsr_1 = deflated_sharpe(r, n_trials=1)
    dsr_50 = deflated_sharpe(r, n_trials=50)
    assert dsr_50 <= dsr_1

def test_durability_by_year_keys():
    dates_ms = (np.arange(504) * 86400000 + 946684800000)  # ~2 years of days from 2000
    r = np.full(504, 0.001)
    d = durability_by_year(r, dates_ms)
    assert len(d) >= 1
    assert all(isinstance(k, int) for k in d)
```

- [ ] **Step 2: Run, verify FAIL.**

- [ ] **Step 3: Implement**

```python
# paper4/code/metrics.py
"""Honest performance metrics: annualized IR, max drawdown, Newey-West t-stat,
Deflated Sharpe Ratio (Bailey & Lopez de Prado 2014), and durability by year."""
from __future__ import annotations
import numpy as np
from datetime import datetime, timezone
from math import erf, sqrt


def ann_ir(r, periods=252):
    r = np.asarray(r, float)
    return r.mean() / (r.std() + 1e-12) * np.sqrt(periods)


def max_drawdown(r):
    eq = np.cumprod(1.0 + np.asarray(r, float))
    peak = np.maximum.accumulate(eq)
    return float((eq / peak - 1.0).min())


def newey_west_t(r, lag=21):
    r = np.asarray(r, float); n = len(r); e = r - r.mean()
    s = np.mean(e * e)
    for l in range(1, lag + 1):
        cov = np.mean(e[l:] * e[:-l])
        s += 2.0 * (1.0 - l / (lag + 1.0)) * cov
    se = np.sqrt(max(s, 1e-18) / n)
    return float(r.mean() / (se + 1e-18))


def _norm_cdf(x):
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


def deflated_sharpe(r, n_trials=1, periods=252):
    """Deflated Sharpe Ratio (Bailey & Lopez de Prado 2014). Per-observation SR vs an
    expected-maximum benchmark from n_trials, scaled by the SR estimation standard error
    (skew/kurtosis adjusted). Returns prob in [0,1]; monotonically decreasing in n_trials."""
    r = np.asarray(r, float); n = len(r)
    mu, sd = r.mean(), r.std() + 1e-12
    sr = mu / sd                                   # per-observation Sharpe
    g3 = np.mean(((r - mu) / sd) ** 3)
    g4 = np.mean(((r - mu) / sd) ** 4)
    # standard error of the SR estimate (skew/kurtosis adjusted)
    se_sr = np.sqrt(max(1.0 - g3 * sr + (g4 - 1.0) / 4.0 * sr ** 2, 1e-9) / max(n - 1, 1))
    # expected maximum Sharpe of n_trials i.i.d. strategies (in SR-standard-error units)
    euler = 0.5772156649
    if n_trials > 1:
        emax = ((1 - euler) * _inv_norm(1 - 1.0 / n_trials)
                + euler * _inv_norm(1 - 1.0 / (n_trials * np.e)))
    else:
        emax = 0.0
    sr0 = se_sr * emax                             # benchmark SR (deflation threshold)
    return float(_norm_cdf((sr - sr0) / se_sr))


def _inv_norm(p):
    # Acklam's rational approximation to the inverse normal CDF
    p = min(max(p, 1e-9), 1 - 1e-9)
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = sqrt(-2 * np.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = sqrt(-2 * np.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5; r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def durability_by_year(r, dates_ms, periods=252):
    r = np.asarray(r, float)
    years = np.array([datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).year for ms in dates_ms])
    out = {}
    for y in np.unique(years):
        rr = r[years == y]
        if len(rr) > 20:
            out[int(y)] = round(ann_ir(rr, periods), 3)
    return out
```

- [ ] **Step 4: Run, verify PASS.**

- [ ] **Step 5: Commit**

```bash
git add paper4/code/metrics.py paper4/code/tests/test_metrics.py
git commit -m "feat(paper4): honest metrics (IR, maxDD, NW-t, DSR, durability)"
```

---

## Task 7: Walk-forward harness

**Files:**
- Create: `paper4/code/harness.py`
- Test: `paper4/code/tests/test_harness.py`

The harness: per-asset apply Kalman + BOCPD column-wise, build weights for a variant, form
next-day returns, apply costs, and (a) on a random-walk universe yield IR≈0 (no look-ahead),
(b) confirm dollar-neutral realized beta≈0. Embargo of `H` days is enforced by zeroing the
last `H` rows of weights so no test bar touches train (the run uses a single pass; the
embargo guard is exercised by the clean-null test).

- [ ] **Step 1: Write the failing tests**

```python
# paper4/code/tests/test_harness.py
import numpy as np
from harness import run_variant, per_asset_states

def _rw_universe(T=600, N=8, seed=0):
    rng = np.random.default_rng(seed)
    return np.cumprod(1 + rng.normal(0.0, 0.01, (T, N)), axis=0) * 100

def test_clean_null_ir_near_zero():
    close = _rw_universe()
    res = run_variant("tsmom", close, k=2, warmup=252,
                      spread_bps=0.0, short_fin_bps_annual=0.0)
    assert abs(res["ir"]) < 0.8            # random walk -> no real edge

def test_states_shapes():
    close = _rw_universe(T=300, N=4)
    vel, sig, sev = per_asset_states(close)
    assert vel.shape == sig.shape == sev.shape == (300, 4)

def test_returns_length_matches():
    close = _rw_universe(T=400, N=5)
    res = run_variant("cpd_momentum", close, k=1, warmup=252)
    assert len(res["net"]) == 400
    assert np.allclose(res["net"][:252], 0.0)
```

- [ ] **Step 2: Run, verify FAIL.**

- [ ] **Step 3: Implement**

```python
# paper4/code/harness.py
"""Walk-forward runner: per-asset belief states -> variant weights -> costed returns -> metrics.
Source of truth for the paper's numbers. Pure-numpy; data is injected as a (T,N) close matrix."""
from __future__ import annotations
import os, sys
import numpy as np

# make the strategy package importable
_STRAT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..",
                                      "Strategies", "slow-momentum-fast-reversion"))
if _STRAT not in sys.path:
    sys.path.insert(0, _STRAT)

from kalman_llt import kalman_llt          # noqa: E402
from bocpd import bocpd_gaussian           # noqa: E402
from signals import build_weights          # noqa: E402
from costs import net_returns              # noqa: E402
from metrics import ann_ir, max_drawdown, newey_west_t, deflated_sharpe  # noqa: E402


def per_asset_states(close, sigma2=None):
    """Apply Kalman LLT + BOCPD to each column. Returns (velocity, trend_sig, severity) (T,N)."""
    T, N = close.shape
    vel = np.zeros((T, N)); sig = np.zeros((T, N)); sev = np.zeros((T, N))
    logc = np.log(np.maximum(close, 1e-9))
    rets = np.zeros((T, N)); rets[1:] = logc[1:] - logc[:-1]
    for j in range(N):
        if not np.isfinite(logc[:, j]).all():
            continue
        out = kalman_llt(logc[:, j])
        vel[:, j] = out["velocity"]
        sig[:, j] = out["trend_sig"]
        s2 = sigma2 if sigma2 is not None else (np.var(rets[1:, j]) + 1e-9)
        sev[:, j] = bocpd_gaussian(rets[:, j], hazard=1 / 250.0, sigma2=s2)
    return vel, sig, sev


def forward_returns(close):
    T, N = close.shape
    fwd = np.zeros((T, N))
    fwd[:-1] = close[1:] / close[:-1] - 1.0
    return fwd


def run_variant(variant, close, k=10, warmup=252, embargo=21,
                spread_bps=5.0, short_fin_bps_annual=300.0, n_trials=3):
    vel, sig, sev = per_asset_states(close)
    W = build_weights(variant, close, vel, sig, sev, k=k, warmup=warmup)
    if embargo > 0:
        W[-embargo:] = 0.0                 # embargo tail (no test bar bleeds past data end)
    fwd = forward_returns(close)
    net = net_returns(W, fwd, spread_bps=spread_bps, short_fin_bps_annual=short_fin_bps_annual)
    active = net[warmup:len(net) - embargo] if embargo > 0 else net[warmup:]
    return {
        "variant": variant, "weights": W, "net": net,
        "ir": ann_ir(active), "max_dd": max_drawdown(active),
        "nw_t": newey_west_t(active, lag=21),
        "dsr": deflated_sharpe(active, n_trials=n_trials),
        "turnover": float(np.nansum(np.abs(np.diff(W, axis=0))) / max(len(W), 1)),
    }
```

- [ ] **Step 4: Run, verify PASS.**

- [ ] **Step 5: Commit**

```bash
git add paper4/code/harness.py paper4/code/tests/test_harness.py
git commit -m "feat(paper4): walk-forward harness (states -> weights -> costed metrics)"
```

---

## Task 8: Data layer (cache-aside S&P 100 close matrix)

**Files:**
- Create: `paper4/code/data.py`

No unit test (live network); follows the `paper1_RL/yahoo_research_data.py` npz cache-aside
pattern. Reuses `trader.data.sources.yahoo.fetch_bars`.

- [ ] **Step 1: Implement**

```python
# paper4/code/data.py
"""Cache-aside (T,N) close matrix for the paper4 universe (Yahoo daily, keyless).
Numeric arrays -> npz; ticker/date metadata -> JSON sidecar. No pickle."""
from __future__ import annotations
import os, sys, json, warnings
from datetime import date
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from trader.data.sources.yahoo import fetch_bars   # noqa: E402
from universe import TICKERS, START, END           # noqa: E402  (run from paper4/code)


def load_close_matrix(cache_path="paper4_close.npz"):
    side = cache_path + ".json"
    if os.path.exists(cache_path) and os.path.exists(side):
        z = np.load(cache_path)
        with open(side, encoding="utf-8") as f:
            meta = json.load(f)
        return z["close"], z["dates"], meta["tickers"]

    start, end = date.fromisoformat(START), date.fromisoformat(END)
    per = {}
    for tk in TICKERS:
        try:
            per[tk] = {r["timestamp"]: r["close"] for r in fetch_bars(tk, start, end, "day")}
        except Exception as e:
            warnings.warn(f"bars {tk}: {e}")
    all_ts = sorted(set().union(*[set(d) for d in per.values()]))
    tickers = [t for t in TICKERS if t in per and len(per[t]) > 252]
    T, N = len(all_ts), len(tickers)
    idx = {ts: i for i, ts in enumerate(all_ts)}
    close = np.full((T, N), np.nan)
    for j, tk in enumerate(tickers):
        for ts, c in per[tk].items():
            close[idx[ts], j] = c
    dates = np.array(all_ts)
    np.savez(cache_path, close=close, dates=dates)
    with open(side, "w", encoding="utf-8") as f:
        json.dump({"tickers": tickers}, f)
    return close, dates, tickers
```

- [ ] **Step 2: Smoke-check import** (no network assertion):
Run: `cd paper4/code && python -c "import data; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add paper4/code/data.py
git commit -m "feat(paper4): cache-aside Yahoo close-matrix loader"
```

---

## Task 9: Run the real walk-forward (the "do we have a result" deliverable)

**Files:**
- Create: `paper4/code/run_paper4.py`

- [ ] **Step 1: Implement the runner** (forward-fills gaps, runs 3 variants, prints the
headline table, saves an equity figure + a JSON of results):

```python
# paper4/code/run_paper4.py
"""Produce paper4's headline results: TSMOM vs cpd_momentum vs belief_gated, net of costs."""
from __future__ import annotations
import os, json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from data import load_close_matrix
from harness import run_variant
from metrics import durability_by_year

FIG = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "figures"))


def _ffill(close):
    out = close.copy()
    for j in range(out.shape[1]):
        col = out[:, j]
        last = np.nan
        for i in range(len(col)):
            if np.isnan(col[i]):
                col[i] = last
            else:
                last = col[i]
    return out


def main():
    close, dates, tickers = load_close_matrix()
    close = _ffill(close)
    print(f"universe: {len(tickers)} tickers, {close.shape[0]} days")
    results = {}
    plt.figure(figsize=(10, 6))
    for variant in ("tsmom", "cpd_momentum", "belief_gated"):
        res = run_variant(variant, close, k=10, warmup=252, embargo=21,
                          spread_bps=5.0, short_fin_bps_annual=300.0, n_trials=3)
        net = res["net"][252:len(res["net"]) - 21]
        dts = dates[252:len(res["net"]) - 21]
        dur = durability_by_year(net, dts)
        results[variant] = {"ir": res["ir"], "nw_t": res["nw_t"], "dsr": res["dsr"],
                            "max_dd": res["max_dd"], "turnover": res["turnover"],
                            "durability": dur}
        plt.plot(np.cumprod(1 + net), label=f"{variant} (IR={res['ir']:.2f})")
        print(f"{variant:<14} IR={res['ir']:+.2f}  NW-t={res['nw_t']:+.2f}  "
              f"DSR={res['dsr']:.2f}  maxDD={res['max_dd']*100:+.1f}%  turn={res['turnover']:.3f}")
    plt.legend(); plt.title("paper4: cumulative net-of-cost equity"); plt.grid(alpha=0.3)
    os.makedirs(FIG, exist_ok=True)
    plt.savefig(os.path.join(FIG, "equity_variants.png"), dpi=120)
    with open(os.path.join(FIG, "..", "results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("\nSaved figures/equity_variants.png and results.json")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it** (live network; from the package dir so imports resolve):

Run: `cd paper4/code && python run_paper4.py`
Expected: a printed table of three variants with IR / NW-t / DSR / maxDD / turnover, and
`figures/equity_variants.png` + `paper4/results.json` written. **Record the numbers** — this is
the answer to "do we have a result".

- [ ] **Step 3: Commit (code + results artifacts)**

```bash
git add paper4/code/run_paper4.py paper4/results.json paper4/figures/equity_variants.png
git commit -m "feat(paper4): walk-forward runner + first real-data results"
```

---

## Task 10: backtrader strategy wrapper (product/CLI path)

**Files:**
- Create: `trader/strategies/cpd_momentum.py`

Thin `BaseStrategy` so `python -m trader strategies` lists it and the CLI can run the
belief-gated variant on the existing Yahoo cache. The research harness (Task 7/9) remains the
source of truth for paper numbers; this is the deployable/product path.

- [ ] **Step 1: Implement** (single-name long/short driven by the per-asset Kalman velocity +
BOCPD gate, reusing the strategy package):

```python
# trader/strategies/cpd_momentum.py
"""Changepoint-aware momentum as a backtrader strategy (single-name long/short).
Velocity sign -> direction; BOCPD severity -> de-risk/flat. Reuses paper4 math units."""
from __future__ import annotations
import os, sys
from dataclasses import dataclass
from typing import ClassVar
import numpy as np
import backtrader as bt

from trader.strategies.base import BaseStrategy

_STRAT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..",
                                      "Strategies", "slow-momentum-fast-reversion"))
if _STRAT not in sys.path:
    sys.path.insert(0, _STRAT)
from kalman_llt import kalman_llt          # noqa: E402
from bocpd import bocpd_gaussian           # noqa: E402


@dataclass
class CpdMomentumParams:
    warmup: int = 252
    sev_exit: float = 0.4          # severity above which we de-risk to flat


class CpdMomentumStrategy(BaseStrategy):
    name: ClassVar[str] = "cpd_momentum"
    description: ClassVar[str] = "Changepoint-aware momentum (Kalman velocity + BOCPD gate)"
    params_dataclass: ClassVar[type] = CpdMomentumParams
    params = (("warmup", 252), ("sev_exit", 0.4))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._closes: list[float] = []

    def next(self):
        self._closes.append(float(self.datas[0].close[0]))
        if len(self._closes) < self.p.warmup:
            return
        logc = np.log(np.asarray(self._closes))
        rets = np.diff(logc, prepend=logc[0])
        vel = kalman_llt(logc)["velocity"][-1]
        sev = bocpd_gaussian(rets, hazard=1 / 250.0, sigma2=float(np.var(rets[1:]) + 1e-9))[-1]
        pos = self.getposition().size
        if sev > self.p.sev_exit:
            if pos != 0:
                self.close(); self.log_trade("close", self.datas[0]._name, pos,
                                             self._closes[-1], "changepoint")
            return
        if vel > 0 and pos <= 0:
            self.order_target_percent(target=0.95)
            self.log_trade("buy", self.datas[0]._name, 0, self._closes[-1], "vel>0")
        elif vel < 0 and pos >= 0:
            self.order_target_percent(target=-0.95)
            self.log_trade("sell", self.datas[0]._name, 0, self._closes[-1], "vel<0")
```

- [ ] **Step 2: Verify discovery**
Run: `python -m trader strategies`
Expected: `cpd_momentum` appears in the listed strategies.

- [ ] **Step 3: Smoke backtest**
Run: `python -m trader backtest cpd_momentum AAPL --from 2018-01-01 --to today`
Expected: runs to completion, prints metrics (Sharpe may be `None` if zero trades — that
guard is intentional per CLAUDE.md).

- [ ] **Step 4: Commit**

```bash
git add trader/strategies/cpd_momentum.py
git commit -m "feat(paper4): backtrader cpd_momentum strategy (CLI/product path)"
```

---

## Task 11: Paper skeleton (academic-paper-writer)

**Files:**
- Create: `paper4/paper_skeleton.tex`
- Create: `Strategies/slow-momentum-fast-reversion/README.md`

- [ ] **Step 1: Invoke the academic-paper-writer skill** at
`etoro/.Claude/Skills/academic-paper-writer` to draft `paper4/paper_skeleton.tex` following
the structure of `paper2_RL`/`paper3` skeletons: Abstract, Introduction, Related Work (cite
Wood & Zohren 2021; Moskowitz 2012; Kalman 1960; Adams & MacKay 2007; Bailey & López de Prado
2014; Lim/Zohren 2019), State-Space Unification (the single-filter result), Changepoint-Gated
Sizing, Experimental Design (pre-registered falsification), Results (insert numbers from
`paper4/results.json`), Scope & Limitations (honesty stance), Conclusion.

- [ ] **Step 2: Write the strategy README** describing the three variants, the math units, and
how to run `paper4/code/run_paper4.py`.

- [ ] **Step 3: Compile** (Greek requires XeLaTeX per paper2 convention):
Run: `cd paper4 && xelatex paper_skeleton.tex && xelatex paper_skeleton.tex`
Expected: `paper_skeleton.pdf` produced.

- [ ] **Step 4: Commit**

```bash
git add paper4/paper_skeleton.tex paper4/paper_skeleton.pdf Strategies/slow-momentum-fast-reversion/README.md
git commit -m "docs(paper4): paper skeleton + strategy README"
```

---

## Self-review notes

- **Spec coverage:** §3 contribution → Tasks 2-4 (unification), Task 4+10 (gating), Tasks 5-9
  (honest eval), Task 10 (eToro/product path stub). §4 architecture units → Tasks 2,3,4,5,6,7.
  §5 data → Tasks 1,8. §6 cross-sectional default → Task 4 `xs_weights` + Task 7 harness.
  §7 evaluation → Tasks 6,9. §8 eToro demo → deferred to a follow-up (Task 10 emits the
  signal; live wiring is its own plan, out of this scope per spec §8).
- **eToro live wiring** is intentionally NOT in this plan (spec §8 marks live scheduling out of
  scope). Task 10 produces the deployable signal; connecting to `back/etoro_api` is a separate
  follow-up plan after the first numbers exist.
- **Type consistency:** `build_weights(variant, close, vel, trend_sig, sev, k, warmup)` used
  identically in Task 4 tests, Task 7 harness. `net_returns(weights, fwd_ret, spread_bps,
  short_fin_bps_annual)` consistent Tasks 5/7. `kalman_llt(...)["velocity"|"trend_sig"|...]`
  keys consistent Tasks 2/7/10. `bocpd_gaussian(x, hazard, sigma2)` consistent Tasks 3/7/10.
- **Import note:** strategy-package modules are imported by bare name (`from kalman_llt import
  ...`) because the harness and tests run with that dir on `sys.path`; the harness adds it
  explicitly (Task 7) and pytest is invoked with both test dirs so each package resolves.
```
