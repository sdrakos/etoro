# paper4 — Changepoint-Aware Time-Series Momentum (design)

**Date:** 2026-06-06
**Status:** design — approved for spec review
**Author:** Stefanos Drakos / AGEL AI
**Home:** `etoro/paper4/` (paper + harness) and `etoro/Strategies/slow-momentum-fast-reversion/` (runnable strategy)

---

## 1. One-line thesis

Slow Momentum with Fast Reversion (Wood & Zohren 2021) uses **two bolted-on parts** — a
trend estimator plus a separate changepoint detector. We show both are read-offs of **one**
Kalman local-linear-trend (LLT) belief: the filtered **trend velocity** is the momentum
signal, and the **standardized innovation / BOCPD run-length** is the "fast reversion" gate.
We evaluate it **honestly and net of costs**, and wire the output to the eToro **demo**
account.

This is the practical bridge between the project's existing research lines:
- borrows the **belief-state machinery** of `paper2_RL` (Kalman LLT + BOCPD),
- borrows the **honest evaluation discipline** of `paper3` (walk-forward, Newey–West,
  Deflated Sharpe, PBO, durability-by-year, cost accounting),
- but its own contribution is **momentum-specific** and **deployment-oriented**.

## 2. Why this is distinct from papers 1–3 (no overlap)

| Paper | Core object | paper4 reuse |
|-------|-------------|--------------|
| paper1_RL (DER) | entropic-reward risk layer | not used directly |
| paper2_RL (Belief-State RL) | POMDP→belief-MDP, HJB, full RL policy | reuse **filter only** (Kalman LLT + BOCPD), **no RL agent** |
| paper3 (Weak-signal pipeline) | PEAD + lead–lag, gate/risk-parity/sizing | reuse **evaluation protocol only** |
| **paper4 (this)** | **changepoint-aware momentum as a single state-space belief** | — |

paper4 does **not** introduce an RL agent (that stays in paper2) and does **not** introduce
new fundamental signals (those stay in paper3). It is deliberately narrow: one signal family
(momentum), one filter (LLT), one gate (changepoint), evaluated honestly, deployed to demo.

## 3. Contribution (4 points)

1. **Unification.** Prove/show that the LLT belief produces both the trend signal
   (`v̂_t`) and the changepoint signal (`ν_t/√S_t`, and BOCPD run-length `r_t`) from a single
   filter, removing the need for a separate GP-changepoint module.
2. **Changepoint-gated sizing.** A sizing rule that de-risks (and optionally flips toward
   mean-reversion) when a regime break is detected — the practical drawdown-control lever.
3. **Honest, cost-aware evaluation.** Walk-forward, Newey–West t, Deflated Sharpe Ratio,
   PBO, durability-by-year, all net of a realistic cost model. A correctly-inferred null is a
   valid outcome.
4. **Deployment.** The strategy emits daily target weights consumable by the eToro demo
   layer (`back/etoro_api`), gated by `QUANTIQ_ALLOW_REAL_EXECUTION` (real stays off).

## 4. Architecture

Three independently-testable units, each one purpose, clear interface.

### 4.1 `kalman_llt.py` — the filter (pure numpy, no IO)
- Input: a 1-D log-price series (per asset).
- Output: per-day belief read-offs:
  `level ℓ̂_t`, `trend velocity v̂_t`, `trend significance v̂_t/√P^{vv}_t`,
  `level gap y_t−ℓ̂_t`, `standardized innovation ν_t/√S_t`.
- Vectorizable across assets. Hyperparameters `(Q, R)` fixed on train, frozen on test.
- This is the LLT recursion in `paper2_RL` Appendix A — port it, do not re-derive.

### 4.2 `bocpd.py` — changepoint detector (pure numpy, no IO)
- Input: the standardized-innovation stream from the filter (or raw returns).
- Output: run-length posterior summary per day — `P(r_t small)` / a scalar **break
  severity** in [0,1] and a boolean break flag at a tuned hazard `H`.
- Adams & MacKay (2007) recursion; Gaussian observation model.

### 4.3 strategy units (in `Strategies/slow-momentum-fast-reversion/`)
Three signal variants sharing one backtest path, so the ablation is apples-to-apples:
- **`tsmom`** — plain time-series momentum (Moskowitz 2012), volatility-scaled. Baseline.
- **`cpd_momentum`** — TSMOM whose trend = filtered `v̂_t`, sized down by break severity.
- **`belief_gated`** — full version: `v̂_t` signal + significance weighting +
  changepoint-gated sizing (de-risk / optional reversion tilt on break).

Each variant exposes the same interface: `signal(prices_df) -> target_weights_df`
(daily, dollar-neutral cross-section **or** single-name long/short — see §6).

### 4.4 `paper4/code/harness.py` — walk-forward evaluator
- Rolling train/test with embargo; hyperparameters fit on train only, frozen.
- Realistic **cost model**: spread + turnover bps; for short legs an **overnight/financing**
  charge (eToro CFD reality). Cost params are explicit and reported.
- Metrics: OOS IR & Sharpe, max drawdown, turnover, realized beta (neutrality check),
  rank-IC, **Newey–West t**, **Deflated Sharpe Ratio**, **PBO**, **durability-by-year**.
- Emits the tables/figures that fill `paper4/paper_skeleton.tex` results section.

### 4.5 backtrader integration (optional, second step)
A thin `BaseStrategy` subclass under `trader/strategies/` that loads frozen filter params and
the chosen variant, so the CLI (`python -m trader backtest cpd_momentum ...`) can run it on the
existing Yahoo cache. The research harness (§4.4) is the source of truth for paper numbers;
the backtrader wrapper is for the product/CLI path.

## 5. Data

- Source: Yahoo daily adjusted (`trader/data` / `yfinance`), keyless.
- Universe: **S&P 100 (decided)**, **as-traded** membership to control survivorship
  (extendable to 500 later). Exact list frozen in `paper4/code/universe.py`.
- Period: 2000–2024 for momentum (no XBRL dependency, unlike paper3).
- VIX available for an optional regime cross-check (already in `paper1_RL` data loader).

## 6. Single-name vs cross-sectional (DECIDED: cross-sectional dollar-neutral is the main)

- **Cross-sectional dollar-neutral** (long top-k velocity / short bottom-k): the honest,
  market-neutral evaluation that matches paper2/paper3 and isolates alpha. **This is the
  paper's primary construction.**
- **Single-name long/short** and **long-only** variants for the **eToro practical path**
  (shorting is expensive on eToro CFDs; long-only avoids financing). Same signal, different
  portfolio constructor. The cost model makes the short-financing penalty visible so we can
  see whether neutral survives or long-only is the pragmatic deployment.

## 7. Evaluation protocol (the "do we have a result" answer)

First deliverable is **one honest number**, not theory:

1. Run the walk-forward on the frozen universe/period.
2. Produce the headline table: **TSMOM vs cpd_momentum vs belief_gated**, each with
   OOS IR, NW-t, DSR, max drawdown, turnover, durability-by-year — **net of costs**.
3. Pre-registered falsification (fixed before the run): a variant is rejected if OOS net-of-cost
   IR < ~0.4, or if DSR-adjusted significance fails, or if durability collapses in the late
   sub-sample. **A null is reported as a null.**
4. The changepoint-gating claim is judged by: does belief_gated reduce max drawdown at known
   regime breaks (2008, 2020) **without** killing IR, vs plain TSMOM?

## 8. eToro deployment (demo only)

- The chosen variant emits daily target weights.
- A small adapter maps weights → eToro instrument orders via `back/etoro_api`
  (`get_server_client`, demo). Real execution stays gated behind
  `QUANTIQ_ALLOW_REAL_EXECUTION` (off).
- Out of scope for this spec: live scheduling, multitenant keys, UI. Paper-trade first.

## 9. Testing

- `kalman_llt`: recovers a known linear trend on synthetic data; innovation spikes at an
  injected level break.
- `bocpd`: fires on a synthetic regime change, quiet on a pure random walk (no false breaks
  beyond hazard rate).
- harness: clean-null check (random-walk universe → IR ≈ 0, t ≈ 0, confirms no look-ahead);
  embargo respected; realized beta ≈ 0 on the dollar-neutral book.
- All tests offline (synthetic fixtures), consistent with repo convention.

## 10. File layout

```
Strategies/slow-momentum-fast-reversion/
  kalman_llt.py          # filter (numpy)
  bocpd.py               # changepoint detector (numpy)
  signals.py             # tsmom / cpd_momentum / belief_gated -> weights
  README.md
paper4/
  code/
    universe.py          # frozen as-traded universe
    harness.py           # walk-forward + costs + metrics (NW, DSR, PBO, durability)
    costs.py             # spread + turnover + short-financing model
  figures/
  paper_skeleton.tex     # written with academic-paper-writer skill, results from harness
docs/superpowers/specs/2026-06-06-paper4-changepoint-momentum-design.md   # this file
docs/superpowers/plans/2026-06-06-paper4-changepoint-momentum-plan.md     # next (writing-plans)
```

## 11. Honesty stance (carried from paper2/paper3)

Better filtering extracts a weak signal more cleanly; it does not manufacture signal.
Realistic target: market-neutral IR 0.5–1.0, and possibly null after real eToro costs. The
paper's value is the unification + the honest, cost-aware, pre-registered evaluation —
whatever the sign of the result. No performance claim is written before the harness produces it.
