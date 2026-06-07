# Methodology & honest evaluation

The discipline that separates a real edge from a backtest mirage. Mirror the existing
`paper4/code/` harness; don't reinvent it.

## Data layer

- **Default source: Yahoo, keyless.** `trader/data/loader.py::load_bars(ticker, start, end, timespan="day", source="yahoo")` is cache-aside (SQLite `~/.etoro/cache.db`, keyed `(ticker, ts, timespan, source)`). `yfinance` `auto_adjust=True`; `end` is exclusive so it fetches `end+1d`; `vwap` is always `None`. Day-only (intraday raises `NotImplementedError`).
- **Massive/Polygon optional** (`source="massive"`, needs `get_massive_key()`, free tier ≈ 2y & 5 calls/min). Sources are isolated in the cache PK — adjusted prices differ slightly, so never mix.
- For a self-contained study, load a price matrix `close (T,N)` aligned on a common date grid, forward-fill gaps, and keep a 252-day warmup you never trade on.

## Leak-free evaluation (the core rule)

- **Nested walk-forward** for any model selection: an outer OOS loop, and inside it an inner split for hyperparameter choice — the test fold is never seen during selection. `paper4/code/dmn.py::nested_walkforward` is the reference.
- **Causal estimates only.** Any vol/feature/scaler at time `t` uses returns strictly before `t`. Rolling vol = `series[t-W:t]`, not whole-period. (The one allowed exception: an *illustration-only* static-vol backtest, clearly labelled, never the serve path.)
- **Costs first.** Apply a realistic spread (`costs.py::net_returns`, ≥5 bps; financing for shorts if modelled) before computing any metric. Report gross **and** net; the net number is the verdict.

## Metric checklist (compute all, report honestly)

- **IR / annualized Sharpe** — but return `None` on zero-trade backtests (`engine/analyzers.py` guard) so a flat strategy isn't shown as catastrophic. Sortino is computed manually from `TimeReturn` (backtrader has no `SortinoRatio`).
- **Newey-West t** — autocorrelation-robust significance of the mean return. Gate signals at |t| ≳ 2.
- **Deflated Sharpe Ratio** (Bailey–López de Prado) — penalizes the Sharpe for the number of trials and non-normality. Use the canonical form (watch the `_inv_norm` sign and the SR std-error scaling — both were bugs once).
- **Durability** — per-year IR/return; a real edge is not one lucky year. Report the table, not just the mean.
- **Max drawdown, turnover** — the cost and pain side.
- **Ablations** — drop each feature/component and show the delta. If removing it doesn't hurt, it was overfitting (parsimony wins).

## Basket diversification gate (measure "diversity > count" before trading)

Before committing a product set, **check its daily-return correlation matrix** — it's the
quantitative form of "diversity > count". Two products at ρ≈0.9 are **one** bet, not two: they add
turnover/cost without a real bet. `paper4/engine/correlation_check.py` (reuses the live eToro fetch)
reports the heatmap, the average |pairwise ρ|, and the **effective number of independent bets**
`ENB = (Σλ)² / Σλ²` over the correlation eigenvalues (= N if all uncorrelated, → 1 if all identical).
Real eToro result that *is* the mechanism behind 5 > 17: the 5-diversified basket (SPY/TLT/GLD/USO/UUP)
has avg |ρ| 0.19 and **ENB 4.2/5 (84%)**, while the 17-ETF set has avg |ρ| 0.38 and only
**ENB 3.9/17 (23%)** — 17 names collapse to *fewer* real bets than 5. Prune redundant high-ρ clusters
instead of padding the count.

## Feature set (the belief-state inputs, per asset)

Ten vol-normalized signals — never the raw price (`paper4/code/features.py`):
1–5. **Multi-horizon returns** (~1m to ~1y) each divided by realized vol (trend vs noise).
6. **Log realized volatility** (current nervousness).
7–9. **Kalman local-linear-trend belief**: velocity, trend significance (`trend_sig`), standardized innovation.
10. **BOCPD changepoint severity** — `R[:kshort].sum()` over the most-recent run-length probs (`kshort=5`). NOT `R[0]` (that equals the hazard and is constant — a real bug we fixed). Fires on a behavior change, not a price tick.

## Models

- **Rules**: a fixed time-series-momentum mapping (`Strategies/.../ts_momentum.py::build_ts_weights`). Transparent baseline.
- **ML**: `DeepMomentumNetwork` (LSTM) trained with a **Sharpe-ratio loss**, selected via nested WF. Beats rules modestly; report the honest gap and its DSR.
- **belief_gated** overlay: mask weak signals by **significance** (`score[|trend_sig| < thr] = nan`) — NOT by magnitude (rank-based weights are magnitude-invariant; masking by magnitude was a bug).

## Sizing (the "how much")

`paper4/code/sizing.py`: `inverse_vol_weights`, `min_variance_weights`, `hrp_weights` (HRP), `ledoit_wolf_cov` (shrinkage — `np.nan_to_num` the window first), `kelly_leverage` (fractional, clipped), and `realized_vol(returns, method="rolling"|"ewma", halflife)` — the selectable vol estimator (rolling = equal-weight; ewma = recency-weighted, reacts faster). Vol-targeting is the profit/risk dial; sizing changes magnitude, rarely Sharpe.

## Gotchas that cost debugging sessions

- EDGAR/fundamentals: `sicCode`→`sic`; SUE winsorization (σ→0 gives absurd std); event-window vs price-window mismatch → OOS 0/0.
- A clean-null test must use a **broad** universe + an NW-t significance check, or it's unstable.
- `paper*/code` shadows stdlib if named `code` and importable — keep no `__init__.py`, run pytest from the dir.
- Binding constraint is usually **data, not method**: depth + small-cap breadth + survivorship-free membership. None are free (see `paper1_RL/DATA_SOURCES.md`).
