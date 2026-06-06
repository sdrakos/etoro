# Slow Momentum with Fast Reversion — paper4 strategy code

Belief-state, changepoint-aware momentum, evaluated honestly and net of costs. This is the
implementation behind `etoro/paper4/` (paper: *From Dead Cross-Sectional Momentum to Belief-State
Deep Time-Series Momentum*).

## The one-line story

The same momentum logic is **dead** on cross-sectional US large-cap equities (net of costs) and
**alive** as **time-series** momentum on a **diversified** asset basket. A small LSTM "Deep
Momentum Network" fed belief-state + changepoint features beats a fixed-rule baseline out of
sample; the edge comes from **asset-class diversity, not name count**.

## Math units (pure numpy, no IO, tested)

| File | What it does |
|------|--------------|
| `kalman_llt.py` | Local-linear-trend Kalman filter → filtered velocity, trend t-stat, standardized innovation |
| `bocpd.py` | Bayesian Online Changepoint Detection (Adams & MacKay 2007) → per-step break severity |
| `signals.py` | **Cross-sectional** builders (`tsmom`/`cpd_momentum`/`belief_gated`) — the *negative* baseline |
| `ts_momentum.py` | **Time-series** multi-horizon momentum (the rules baseline that the ML must beat) |

Tests: `cd Strategies/slow-momentum-fast-reversion && python -m pytest tests -q`

## The three strategy "drivers"

1. **Rules time-series momentum** (`ts_momentum.build_ts_weights`) — fixed multi-horizon trend
   sign, inverse-vol sizing, monthly rebalance, optional BOCPD de-risk. No learning. OOS IR ≈ 0.47.
2. **ML Deep Momentum Network** (`paper4/code/dmn.py`) — one shared LSTM, per-asset position in
   [-1,1], trained on a portfolio Sharpe loss net of costs, hyper-params chosen by a **nested**
   walk-forward (validation-only, never touches test). OOS IR ≈ 0.58 (DSR 0.67).
3. **Return-stacked overlay** — full equities + a half-sized trend sleeve; beats buy-and-hold S&P
   out of sample (see `paper4/figures/etf_beat_buyhold.png`).

## Reproduce

```bash
cd paper4/code
python run_etf.py        # nested-OOS ML vs rules vs SPY + figures + results_etf.json (~3-5 min)
```

Data is free Yahoo daily (cached to `etf_close.npz`, gitignored). Everything is net of a
transparent cost model (spread on turnover + short financing). Nulls are reported as nulls.
