# Positioning (position-sizing) strategies — what & where

"Positioning" = how much capital each position gets and how much total leverage the book runs.
Sizing changes **magnitude and drawdown**; it raises **Sharpe** only via better allocation or a
better signal, never via leverage alone. Naive Kelly / mean-variance overfit and blow up — use the
**robust** variants (fractional, shrinkage, HRP).

## The strategies (each with its source paper + our implementation)

| Strategy | What it does | Bibliography (PDF) | Code |
|----------|--------------|--------------------|------|
| **Inverse-vol** (baseline) | weight ∝ 1/σ; calm assets get more | Moreira & Muir 2017 | `paper4/code/sizing.py::inverse_vol_weights` |
| **Mean-variance / min-variance** | classic risk/return optimization | Markowitz 1952 | `min_variance_weights` |
| **Ledoit-Wolf shrinkage cov** | robust covariance (fights estimation error) — feed it to any optimizer | Ledoit & Wolf 2004 | `ledoit_wolf_cov` (`np.nan_to_num` the window first) |
| **HRP** (Hierarchical Risk Parity) | clustering-based risk budgets; stable OOS, no matrix inversion | López de Prado 2016 (HRP) | `hrp_weights` (+ `_quasi_diag`, `_cluster_var`) |
| **Fractional Kelly leverage** | growth-optimal total leverage; ¼–½ Kelly for safety | Kelly 1956; Thorp 2006 | `kelly_leverage(returns, fraction, cap)` |
| **Volatility targeting** (the risk dial) | lever up/down to a target annual vol; `rolling` or `ewma` estimate | Moreira & Muir 2017 | `realized_vol(returns, method="rolling"\|"ewma")` + the engine's `_vol_target_capital` |
| **Differential-Sharpe / direct RL** | the LSTM's Sharpe-ratio loss *is* this sizing rule, learned | Moody & Saffell 2001 | `paper4/code/dmn.py` (`sharpe_loss`) |

## Where to find everything (exact paths under `etoro/`)

- **Papers (PDFs, one folder each):** `Bibliography/position-sizing/` — Kelly 1956, Thorp 2006, Markowitz 1952, Ledoit-Wolf 2004, Moreira-Muir 2017 (free); Moody-Saffell 2001, Grinold 1989, López de Prado 2016 HRP (paywalled — content covered by held textbooks, see `Bibliography/position-sizing/INDEX.md`).
- **Index / takeaway:** `Bibliography/position-sizing/INDEX.md` (which paper, why it matters, the practical levers).
- **Implementations:** `paper4/code/sizing.py` (all of the above, pure + unit-tested in `paper4/code/tests/test_sizing.py`).
- **Comparison runner + results:** `paper4/code/run_sizing.py` → `paper4/results_sizing.json` (inverse-vol vs HRP vs min-var vs ¼/½/full Kelly vs ML vs buy&hold, 17y OOS).
- **Figures:** `paper4/figures/fig_sizing.png` (sizing comparison), `fig_alloc_2022.png` / `bt_alloc_2022crisis.png` (allocation in the 2022 crash), `bt_ml_alloc.png` / `bt_alloc_recent.png` (recent book). The **positioning diagram** sits inside the paper's references section in `paper4/paper_skeleton.tex`.

## How to use them in a new model

1. Start from **inverse-vol or HRP** on a **Ledoit-Wolf** covariance for allocation across the basket.
2. Apply **volatility targeting** (`realized_vol`, causal rolling by default; ewma for faster reaction) as the user-facing **risk dial**.
3. Offer **fractional Kelly** as the "increase profit" lever — but always show that it raises drawdown proportionally, and prefer ¼–½ Kelly.
4. Report each variant in the results table (Sharpe / CAGR / maxDD / final), exactly as `results_sizing.json` does, so the trade-off is explicit and honest.
