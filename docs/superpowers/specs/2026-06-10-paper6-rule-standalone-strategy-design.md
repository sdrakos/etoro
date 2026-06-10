# paper6 — The Rule as a Standalone Strategy (design spec)

**Date:** 2026-06-10
**Status:** approved (brainstorming) → ready for writing-plans
**Method:** built to the `ai-trading` skill standard (Source → Reproduce/critique → Evolve → Evaluate honestly → Deploy to eToro → journal paper → business report).

## 1. Purpose & contribution

Across paper4/paper5 the **fixed rule** — per-asset time-series momentum (sign of trend) × **volatility-target sizing** (causal rolling/EWMA) over a **diversified basket**, with a **no-trade band** — was always the *baseline* we tried to beat with ML. It was the only universally-robust player: it won or tied in both the crypto (high-alpha) and ETF (low-alpha) regimes, and no ML model beat it consistently net-of-cost OOS.

**paper6 flips the framing: the rule becomes the protagonist.** The research question is twofold:
1. **Is the rule robust enough to deploy as an independent, standalone strategy?** (not as a baseline)
2. **How can it be improved for practical use — without overfitting?**

**Novel contribution (journal):** *"When the simple rule is enough."* A disciplined robustness study (parameter-stability surfaces establishing the win is not tuned) plus a pre-registered ablation of which risk-overlays *actually* help net-of-cost OOS versus which overfit — establishing the rule as a deployable product with a measured risk/return profile and a public capital dial.

**Honest prior:** we already know the rule stands; the open question is *which improvements survive net-OOS*. Several may not — that is reported as a null (the `ai-trading` "report the nulls" discipline). The value is the established, measured, deployable rule, not alpha promises.

## 2. Folder layout

Built in the paper4/paper5 style (bare-import tests, no `__init__.py`, run `pytest` from the dir; figures git-ignored globally, `git add -f` the ones we keep).

```
paper6/
├── code/
│   ├── rule.py          # THE RULE as a pure function: signal → vol-target → band. Single source of truth.
│   ├── data.py          # 5-asset loader (Yahoo deep + npz cache), reuses trader/data
│   ├── overlays.py      # BOCPD brake, VIX/regime gate, drawdown-control (each toggleable, off by default)
│   ├── robustness.py    # sensitivity grid (lookback/band/target-vol/rebalance)
│   ├── basket.py        # ENB-maximizing greedy selection around the 5-asset core
│   ├── sizing_dial.py   # vol-target↔risk-budget mapping, fractional-Kelly, EUR returns
│   ├── eval.py          # leak-free walk-forward, net@costs, NW-t, DSR, durability-by-year
│   ├── run_robustness.py / run_overlays.py / run_basket.py / run_sizing.py   # ablation drivers → figures
│   └── tests/           # offline unit tests
├── engine/              # eToro standalone-rule engine + real-price backtest (paper4 patterns)
│   ├── cli.py           # signal / execute (demo-gated) / recalibrate
│   ├── etoro_backtest.py
│   └── tests/           # offline, mocked eToro client
├── figures/             # *.png (git add -f)
├── paper_skeleton.tex/.pdf   # journal paper (EN)
└── report_GR.tex/.pdf        # business report (GR, XeLaTeX)
```

**Critical principle — `rule.py` is the single source of truth.** The rule is defined once as a pure function; the research harness AND the engine call the same implementation. No two implementations that drift.

## 3. Universe & data

- **Primary deployment universe:** `SPY, TLT, GLD, BTC, UUP` — the proven ENB-4.5 "sweet spot" (5 uncorrelated > 14 redundant), all eToro-available.
- **Data — research/durability:** Yahoo deep (`yfinance`, `auto_adjust=True`), as deep as each name allows (SPY/TLT/GLD/UUP ~2005, BTC ~2014) for robustness + durability-by-year (incl. 2008/2020/2022 where coverage allows; BTC limits the joint window).
- **Data — deployment validation:** real eToro candles (~4y, the 14 assets that resolve on eToro from paper5) with **real per-asset spreads** (BTC ~31 bps, ETFs 1–4 bps) — never a flat spread.
- **Costs:** net of real per-asset spreads always. A direction flip costs double (close + open).

## 4. The four research axes (pre-registered)

Each axis pre-registers *before running* what is measured and what counts as a "win" — otherwise it is data-snooping. Shared gate: **net @ real spreads, leak-free WF, NW-t, durability-by-year (incl. 2022).**

### Axis 1 — Robustness / anti-overfit (run first; defines the base)
- Grid: lookback ∈ {21, 42, 63, 126, 252}d; band ∈ {0, 0.05, 0.10, 0.15, 0.20, 0.30}; target-vol ∈ {0.10, 0.15, 0.20}; rebalance ∈ {daily, weekly}.
- Output: net-IR **heatmap surfaces**.
- **Win = a wide, stable OOS region** (not a sharp peak). The chosen base config is taken from the **center** of the stable region, **not** the argmax — this is the anti-overfit move.
- Delivers: the "base config" the other three axes build on.

### Axis 2 — Risk overlays (each ablated vs base, individually AND combined)
- **BOCPD brake** (from paper4): cut exposure on changepoint. Pre-registered: "reduces maxDD ≥20% without lowering net-IR by >0.1".
- **VIX/regime gate:** de-risk when ^VIX > rolling threshold. Same pre-registered gate.
- **Drawdown-control:** reduce size when trailing drawdown > X%.
- **Win per overlay** = passes its pre-registered gate net-OOS **and** improves 2022. Otherwise → **null** (reported honestly; stop-loss is already known to hurt and is not re-litigated as an overlay, only cited).

### Axis 3 — Basket / diversification (ENB as the selection objective)
- Greedy ENB-maximizing selection over a pool {5-asset core + optional QQQ/EEM/HYG/SLV/…}. Compare 3/5/7 assets.
- **Win = the ENB-selected basket improves IR/maxDD vs the fixed 5-asset** — or confirms 5 is already saturation (also a result, consistent with the "diversity saturates ~5" prior).

### Axis 4 — Sizing / capital dial (from IR to real money)
- vol-target ↔ risk-budget mapping (what target-vol for a target maxDD); **fractional-Kelly** comparison; **EUR returns** on €10k with leverage scenarios; capacity vs turnover/costs.
- **Win = one clear, safe dial** the end user turns — exposed as `conservative / balanced / aggressive` presets.

### Final synthesis
Winning config = base (Axis 1) + whichever overlays passed (Axis 2) + basket (Axis 3) + dial (Axis 4). This config goes to the engine.

## 5. eToro standalone-rule engine

`paper6/engine/`, in the paper4 style:
- `cli.py`: `signal` (target positions for the 5-asset basket from eToro candles, via `rule.py` + winning config) / `execute` (**demo-gated**, `--execute` flag, close by positionID) / `recalibrate` (re-estimate causal vol/band params — the rule has no "train", only re-estimation).
- `etoro_backtest.py`: real-price walk-forward on ~4y eToro candles (14-asset resolved), real per-asset spreads, with the overlays that passed. Produces the real-price confirmation + EUR-returns probe.
- `--preset {conservative, balanced, aggressive}`: the Axis-4 capital dial as a public knob.
- **Safety:** real execution behind `QUANTIQ_ALLOW_REAL_EXECUTION` + explicit `--execute`. Demo first, always.
- Offline tests with a mocked eToro client (paper4 pattern).

## 6. Deliverables (full ai-trading arc)

- **Journal paper** (`paper_skeleton.tex`, EN) via the `academic-paper-writer` skill: contribution as in §1; TikZ pipeline, robustness heatmaps, overlay-ablation table, basket ENB figure, EUR-returns/dial figure, durability-by-year (incl. 2022). Cites paper4/5 by title `(Drakos 2026)`.
- **Business report** (`report_GR.tex`, GR, XeLaTeX): non-technical, QUANTIQ cover, all tables/figures, plain language ("a simple, stable strategy; here is its risk/return; here is the dial"). Cites the paper.

## 7. Testing & build discipline

- Offline unit tests per module: `rule.py` (signal/vol-target/band correctness), `overlays.py` (each overlay), `eval.py` (leak-free assertions — vol/params use only the past), engine (mocked client).
- Every quantitative claim is **numerically verified before** it is written into the paper (the `academic-paper-writer` rule).
- Build path: brainstorming → writing-plans → subagent-driven-development. Opus for every dispatched subagent. No `Co-Authored-By` in commits.

## 8. Non-negotiables (from the ai-trading skill)

- Net of costs or it doesn't count.
- Leak-free always (nested/walk-forward; causal vol = `close[-W:]` re-estimated each step).
- Out-of-sample and broad; report where it breaks.
- Diversity > count.
- Demo first; real-money execution gated.
- Report the nulls.
- Originality stated explicitly (§1).
