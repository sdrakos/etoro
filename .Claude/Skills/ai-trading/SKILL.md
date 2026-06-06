---
name: ai-trading
description: >-
  Develop a quantitative / AI trading model end-to-end the QUANTIQ way: start from a bibliography
  paper, evolve it on free Yahoo data with an honest, leak-free, cost-aware backtest, deploy it as
  an eToro engine (demo first, real gated), and produce BOTH a novel journal paper and a
  non-technical business report (LaTeX/PDF). Use when building or iterating a trading strategy or
  model, reproducing/improving a trading paper, adding an eToro trading engine or real-price
  backtest, or writing the accompanying paper/report. Triggers: "νέο μοντέλο/στρατηγική", "υλοποίησε
  αυτό το paper", "eToro engine/backtest", "γράψε το journal paper / business report".
---

# AI Trading (QUANTIQ method)

This skill encodes the **repeatable pipeline** behind `paper4` and the QUANTIQ engine: take a real
idea from the literature, **evolve it honestly** on free data, **ship it to eToro**, and **write it
up** as both a peer-grade paper with a genuine novel contribution and a plain-language business
report. Every new model follows the same arc.

## The pipeline (always these phases, in order)

1. **Source** — pick a serious paper (ML/RL/AI in trading) with a *testable* idea. One model = one folder.
2. **Reproduce & critique** — rebuild the core claim, then stress it: does it survive **net of costs**, **out-of-sample**, on a **broad** universe? Most published edges do not. Write down what dies.
3. **Evolve** — add the QUANTIQ machinery that has actually worked: belief states (Kalman LLT + BOCPD), a **diversified asset basket**, **volatility targeting**, principled **positioning/sizing** (Kelly, HRP, shrinkage, vol-target — papers + code in `references/positioning-strategies.md`). Improve the original, don't just re-run it.
4. **Evaluate honestly** — leak-free **nested walk-forward**, net-of-cost returns, **Newey-West t**, **Deflated Sharpe**, durability, ablations. No look-ahead, no silent caps. → `references/methodology-and-evaluation.md`.
5. **Deploy to eToro** — a `signal / execute(demo, gated) / retrain` engine + a **real-price backtest** on eToro candles. Train on Yahoo (deep), serve on eToro. → `references/etoro-engine.md`.
6. **Write the journal paper** — frame the **novel contribution** explicitly, admit scope honestly. Use the `academic-paper-writer` skill. → `references/paper-and-report.md`.
7. **Write the business report** — a non-technical LaTeX/PDF for executives/investors, with the cover, all result tables + figures, and the paper cited by title `(Drakos <year>)`. Template: `assets/report_template.tex`.

Scaffold a fresh model folder with everything wired:
`python .Claude/Skills/ai-trading/scripts/new_model.py <name> --path <dir>`

## Non-negotiable principles (the "honest" in the work)

These are not style preferences — violating them produces fake results that die in live trading.

- **Net of costs or it doesn't count.** Always report after a realistic spread (≥5 bps). A gross edge that vanishes net is not an edge — say so.
- **Leak-free always.** Training and vol/feature estimates use **only the past**. Nested walk-forward for any model selection. A rolling vol is `close[-W:]` re-estimated each step, never the whole-period std at serve time.
- **Out-of-sample and broad.** A signal that only works on a narrow, survivorship-biased universe is an artifact. Test breadth; report where it breaks.
- **Diversity > count.** The lever is asset-class diversity / low correlation, **not** the number of names. 5 uncorrelated beats 17 redundant. Don't pad the basket.
- **Demo first.** Real-money execution is gated behind an explicit flag (`QUANTIQ_ALLOW_REAL_EXECUTION` / `--execute`). Never auto-trade real money without the user's explicit, in-context go-ahead.
- **Report the nulls.** If the evolved model fails, the honest null **is** the paper (cf. `paper3`). Don't reframe a null as a win.
- **Originality each time.** Every journal paper must state a contribution that isn't already in the source paper — a new mechanism, combination, honest negative result, or deployment artifact.

## Repo conventions (don't relearn these)

- **Data is keyless by default.** Yahoo via `yfinance` (`auto_adjust=True`), deep history, free. Massive/Polygon is optional (`--source massive`, needs key). The cache (`~/.etoro/cache.db`) is keyed by `(ticker, ts, timespan, source)` — sources never collide. `load_bars` is day-only.
- **Secrets live ONLY in `back/.env`** — `MASSIVE_KEY`, `ETORO_PUBLIC_KEY`, `ETORO_PRIVATE_KEY`, `FINNHUB_API_KEY`, `GIT_HUB_TOKEN`, Graph email creds. Never duplicate, hardcode, or print them. Mask tokens in any command output.
- **Train on Yahoo, serve on eToro.** Both `rules` weights and the ML model derive from Yahoo bars; the live signal runs on eToro candles. There is a mild adjusted-price skew between providers — vol-normalized features mitigate it.
- **Bare-import test convention** in `paper*/code` and `paper*/engine`: no `__init__.py`, run `pytest` from the directory. Tests are fully offline (the eToro client is mocked).
- **No `Co-Authored-By`** in commits; clean `git commit -m`. Use **Opus** for every dispatched subagent. Conversations Greek/Greeklish; code + papers English (business report is Greek unless asked).
- **Figures are git-ignored globally** (`*.png`) — `git add -f` figures you must commit, like the existing `paper4/figures/*`.

## What has actually worked (proven on real eToro prices, net, OOS)

Carry these priors into every new model; re-verify, don't assume:
- Cross-sectional equity momentum is **dead** net of costs; **time-series** momentum on a **diversified** basket is alive. BOCPD reduces drawdown, not alpha (a "smart brake" on regime change, not a price stop).
- ML LSTM Deep Momentum Network (belief + changepoint features, nested WF) ≈ IR 0.58 > fixed rules 0.47.
- **Long-only wins in bulls** (loses crisis protection); **vol target is the profit/risk dial** (profit ∝ vol); **stop-loss HURTS** (whipsaw — tested, raises drawdown).
- eToro: opens work live on demo; **17/18 ETFs available** (DBC missing, BTC available).

## Build discipline

For non-trivial new work, go through **brainstorming → writing-plans → subagent-driven-development**
(the superpowers skills). Numerically verify any quantitative claim **before** writing it into a
paper (the `academic-paper-writer` rule). Keep the engine's offline test suite green.

## Reference files

- `references/methodology-and-evaluation.md` — data layer, leak-free walk-forward, cost model, the honest-evaluation metric checklist (NW-t, DSR, durability), feature set, the gotchas.
- `references/positioning-strategies.md` — the position-sizing strategies (inverse-vol, min-variance, Ledoit-Wolf, HRP, fractional Kelly, vol-targeting, differential-Sharpe), each with its **bibliography PDF** (`Bibliography/position-sizing/`) and **implementation** (`paper4/code/sizing.py`), plus where the comparison results/figures live.
- `references/etoro-engine.md` — engine architecture (`signal/execute/retrain`), the **exact eToro endpoints** (`/api/v1/...`, `{SEG}`), the API quirks (search `items[]`, close by positionID, double-nested candles), vol-targeting (rolling/ewma, causal), real-price backtest, safety gating.
- `references/paper-and-report.md` — journal-paper novelty framing + honest scope; the business-report recipe (XeLaTeX Greek, cover, tables/figures, `(Drakos year)` citation).
