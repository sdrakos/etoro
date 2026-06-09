# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`etoro/` is **one** quantitative-trading project whose components share the same
`back/.env` secrets and data conventions:

- **`back/`** — FastAPI layer. (a) Wrapper over the Massive.com (Polygon.io rebrand) REST API, 104 endpoints across 9 routers; (b) the eToro Public API integration (`back/etoro_api/` typed client + vault, `back/routers/etoro/` proxy/social/portfolio/order routers) for the user's real eToro account. Used directly via HTTP or imported by other tools.
- **`front/`** — **QUANTIQ** web app (React + Vite + TanStack Query/Table + Tailwind). A live eToro **Screener** (category browse + exchange filter + WebSocket live prices) and a **Portfolio** view (open positions + live P&L + close). Talks only to `back/` over the Vite dev proxy. See the QUANTIQ section below.
- **`trader/`** — Phase 1 Python backtesting framework on backtrader. Strategy-agnostic: adding a new strategy is dropping one file under `trader/strategies/`. Default data source is Yahoo (keyless); Massive optional via `--source`.
- **`paper1_RL/`** — Research component: the **Differential Entropic Reward (DER)** paper (`der_paper_full.tex/.pdf`) plus its reproducibility code. Includes the signal-engine + DER-risk-layer alpha experiments (PEAD, sector-neutral momentum, VIX-driven θ) validated on Yahoo 2015–2024 — see `docs/superpowers/specs|plans/2026-06-03-der-alpha-signal-engine*`.
- **`paper2_RL/`** — follow-on research (in progress).
- **`paper3/`** — *"A Disciplined Pipeline for Weak Cross-Sectional Equity Signals"* (PEAD + same-industry lead-lag + utility gate + risk-parity + regime sizing). Built/validated by the `quantiq-pead` skill below.
- **`paper4/`** — *"From Dead Cross-Sectional Momentum to Belief-State Deep Time-Series Momentum"* + a **demo-verified eToro deployment engine**. `paper4/code/`: Kalman LLT + BOCPD belief states feeding a fixed-rule **TSMOM** and an **LSTM Deep Momentum Network** (`dmn.py`, **nested leak-free walk-forward** selection), honest cost-aware eval (Deflated Sharpe, durability). Honest arc (all OOS, net): cross-sectional equity momentum is **dead**, time-series momentum on a **diversified** ETF basket is alive; **diversity > count**; **long-only wins in bulls** (loses crisis protection); **vol-target is the risk/profit dial**; **stop-loss hurts** (whipsaw — tested); BOCPD is the "smart brake". `paper4/engine/`: a CLI (`cli.py`: `signal`/`execute` demo-gated/`retrain`, `--target-vol`, `--vol-method rolling|ewma` — **selectable causal vol-targeting** (trailing-63d rolling or recency-weighted EWMA via `sizing.realized_vol`, front-end-ready), `--strategy rules|ml`) that **opens orders live on the eToro demo** (close by **positionID**; search uses the `items[]` key; **17/18 ETFs on eToro**, DBC missing, BTC available), plus `etoro_backtest.py` on **real eToro candles** (~4y; `--vol-method static|rolling|ewma` + `--compare-vol` overlay — on real prices the causal rolling slightly *beat* static at the same maxDD), `dashboard.html`, and a non-technical **business report** `report_GR.tex/.pdf` (XeLaTeX/Greek, polyglossia, QUANTIQ "Deep Learning Trading" cover, all result tables+figures, cites the paper by title as `(Drakos 2026)`, incl. a measured **diversification section**); plus `engine/correlation_check.py` (**basket-diversification gate**: daily-return correlation heatmap + **effective number of independent bets** ENB=(Σλ)²/Σλ² — on real eToro prices the 5-diversified set scores ENB 4.2/5 vs the 17-ETF set's 3.9/17, the *measured* mechanism behind "diversity > count"), and two Greek beginner **seminars** `lstm_tutorial_GR.tex/.pdf` (neural-net + LSTM theory → our DMN) and `belief_states_tutorial_GR.tex/.pdf` (Kalman LLT + BOCPD belief features), both grounded in the real `dmn.py`/`kalman_llt.py`/`bocpd.py`. Train on Yahoo (deep), serve on eToro. **27 offline tests** (mocked client). Specs/plans: `docs/superpowers/specs|plans/2026-06-06-paper4-changepoint-momentum*` and `*-etoro-engine*`.
- **`paper5/`** — intraday (1h/4h) deep-momentum project (built via the `ai-trading` skill; basis = DMN Lim 2019 + Momentum Transformer Wood 2022; data = Yahoo). **Phase-2 (cost-survivability) done** — findings below. `code/`: `cost_survivability.py` + `_v2.py` (turnover-reduction + crypto + deep daily), `regime_stress.py` (durability-by-year incl. 2022). `engine/etoro_cost_check.py`: live eToro bid/ask via `/api/v1/market-data/instruments/rates`. `tutorial_tests_GR.tex/.pdf`: Greek beginner explainer of the tests (IR, turnover, break-even, with a worked numeric example). **Phase-3 (DMN build) done** — findings below. `code/`: `crypto_data.py`/`combined_data.py` (8-crypto + 18 crypto+ETF daily, npz cache), `crypto_features.py` (wraps paper4 `build_features` → the 10 belief-state features), `models.py` (paper4 LSTM DMN + new **block-local causal MomentumTransformer**, O(T·W)), `band_eval.py`, `train_eval.py` (model-agnostic leak-free nested WF + DSR + net@costs, `ppy` selectable), `diversification_check.py` (**ENB gate**), `run_dmn_crypto.py`/`run_dmn_combined.py` (ablation drivers). 16 offline tests.
- **`tutorials/`** — Greek beginner explainers (XeLaTeX/DejaVu Serif), e.g. `signals_tutorial_GR.tex` (signals: IC, IR, Newey-West t, gate, √N combination, risk parity).
- **`.Claude/Skills/ai-trading/`** — the reusable **QUANTIQ model-development skill** that encodes the paper4 pipeline: source a bibliography paper → reproduce/critique → evolve on free **Yahoo** data → honest **leak-free, cost-aware** backtest → **eToro engine** (demo first, real gated) → a **novel journal paper** + a non-technical **business report**. `references/`: `methodology-and-evaluation.md` (nested walk-forward, NW-t/DSR/durability, the 10 belief-state features, gotchas), `positioning-strategies.md` (inverse-vol/min-var/Ledoit-Wolf/HRP/fractional-Kelly/vol-target/differential-Sharpe — each mapped to its `Bibliography/position-sizing/` PDF + `paper4/code/sizing.py` impl + results/figures), `etoro-engine.md` (the **exact `/api/v1/…{SEG}` endpoints** + API quirks + gating), `paper-and-report.md` (novelty framing + the XeLaTeX-Greek report recipe). `assets/report_template.tex` (cover+intro, compiles) and `scripts/new_model.py` (scaffold). Use it whenever building/iterating a trading model, an eToro engine/backtest, or the accompanying paper/report.
- **`.Claude/Skills/quantiq-pead/`** — the SEC-EDGAR PEAD/lead-lag engine: point-in-time SUE from EDGAR (no analyst data), Fama-MacBeth own/peer separation, drift/half-life/durability event study, risk-parity combination. `analysis/run_big_universe.py` orchestrates own-PEAD + lead-lag on a wide price panel. `skill/sec-edgar/scripts/fundamentals_api.py` is the consolidated endpoint: `get_fundamentals(ua, tickers)` → all PiT line items in one call, `fundamental_factors(panel)` → value/quality/accruals/investment/buyback factors (the orthogonal signals to combine with PEAD).
- **`Bibliography/`** — curated literature. `intraday-dl-rl-trading/` is an annotated bibliography (`README.md`) of **reputable-only** papers (Oxford-Man/Zohren-Roberts, IEEE TSP/TNNLS, Quant Finance, EJOR, ICML, AAMAS, Math Finance — predatory/paper-mill venues excluded) on LSTM/DMN, RL, and CNN/LOB for intraday (1h/4h) trading, with `download_pdfs.py` (arXiv PDFs are gitignored — re-downloadable). Foundation for the **planned intraday project** below.

Phase status, layout, and end-user CLI examples live in `README.md` — don't duplicate them here.

### Real-data PEAD findings (2026-06, free EDGAR + Yahoo)

Honest, fragile results — **signals are universe/period-dependent** (the paper3 thesis, demonstrated live):
- **own-PEAD**: null on mega-caps (150 names, t=1.2) but **significant when mid-caps included** (401 names 2015-2024, OOS IR 0.74, NW t=2.54, durable) — matches theory (PEAD stronger in smaller names).
- **same-industry lead-lag**: significant only on the narrow 150 mega-cap universe (t=2.61); **null on the broad 401** (t=0.10) → small-universe artifact, fragile.
- **fundamentals** (9 theory-signed value/quality/accruals/investment/buyback factors via `fundamentals_api`): **all fail the gate** at every horizon (monthly→annual). 2015-24 = "value winter" + only ~3 independent annual obs → sample too short for slow factors.
- **net of costs the edge vanishes**: own-PEAD long-short gross +11.2% / IR 0.75, but **net of 5bps spread → +0.1% / IR 0.02** (maxDD −4.2%). A real but economically razor-thin signal; not tradable alone.
- Three real bugs fixed in the skill to get here: EDGAR `sicCode`→`sic`; SUE winsorization (σ→0 gave std 840); event-window filter (events 2011-2026 vs prices → OOS=0/0).
- **Binding constraint is data, not method**: need depth + small-cap breadth + survivorship-free membership (Sharadar/CRSP). None free; see `paper1_RL/DATA_SOURCES.md`.
- Written up in **`paper3/paper_skeleton.tex`** (9 pp, TikZ pipeline + drift/cross-config/fundamentals/PnL figures; honest null). Figures live in `paper3/figures/` (gitignore has a `!paper3/figures/*.png` exception over the global `*.png` ignore — keep it).

### News / sentiment data availability (2026-06, checked live)

Whether per-instrument news/analysis is usable as a model feature — verified against the actual APIs, not assumed:
- **eToro**: NO news/analyst/sentiment endpoints. Only a **social feed** (`GET /api/v1/feeds/instrument/{marketId}` — user discussion posts, raw text, no sentiment score) and user-discovery analytics (about people, not markets). `market-data` is price/metadata only.
- **SEC EDGAR (`quantiq-pead`)**: fundamentals/earnings (PiT SUE/PEAD), **back to ~2009–2011** (XBRL). NO news — the skill explicitly forbids narrative "analysis".
- **Finnhub (free tier, `FINNHUB_API_KEY` in `back/.env`)**: `company-news` returns **only the last ~1 year** (≈250 articles/symbol cap, regardless of the requested `from`; **ETFs ARE covered** — TLT/GLD/USO/UUP ~250 each); `stock/earnings` surprises = **last 4 quarters only**; `news-sentiment` = **403 (premium)**.
- **Binding conclusion — depth kills news as a training feature.** The DMN trains on 2007–2024 (17y); free news reaches ~1y, so there is no honest leak-free way to backtest a news/sentiment signal over the model's history. Deep news archives (RavenPack/Bloomberg) are paid. Free news is usable only **forward/live** or for a short recent OOS slice. (Same lesson as fundamentals: the constraint is data, not method.)

**RSS is forward-only, not an archive.** No news site's RSS (Reuters, AP, CNBC, MarketWatch, Yahoo, Nasdaq, Google News, SEC) gives historical depth — RSS exposes only the latest ~20–200 items / last days–weeks. RSS's role is to *accumulate forward* (poll daily, store), not to backfill. Choosing a different site's RSS does not solve depth.

**Free deep-historical news/sentiment sources (for later, not yet wired):**
- **GDELT Project** ⭐ — global news monitor, 100+ languages, every 15 min. **Events** back to **1979**; **GKG** (Global Knowledge Graph, themes + entities + **built-in tone/sentiment**) back to **Feb 2015**. Free via **bulk CSV** or **BigQuery** (`gdelt-bq`). The easy **DOC 2.0 API is recent-only (~3 months)** and **rate-limits hard (429) from datacenter IPs** — confirmed: blocked from this env, run it from a user IP. Depth needs BigQuery/bulk. Entity/theme-centric (good for *gold/oil/Fed*, weak for ticker `SPY/TLT` — needs product→theme mapping). **The only free source that fits our macro/commodity basket.**
- **Common Crawl News (CC-NEWS)** — free WARC archives of news since **2016**; raw text only (no sentiment), terabytes, no finance filter → run our own NLP.
- **FNSPID** (2024 research dataset) — ~15M news records **aligned with prices**, **~1999–2023**, ~4–6k **US stocks**; partial LLM sentiment. Best fit *if we ever model stocks* (not ETFs/macro).
- **Kaggle financial-news dumps** — community datasets (e.g. 2009–2020); convenient but heterogeneous, opaque provenance, **no PiT guarantee** (look-ahead/survivorship risk) — treat with suspicion for honest backtests.
- **SEC EDGAR full-text** (`efts.sec.gov`, **2001+**) — official filings, not news; **8-K = official corporate news**, PiT-accurate; already used via `quantiq-pead`. US stocks only.
- Fit summary: **GDELT** for our macro/ETF basket (themes); **FNSPID/EDGAR** for a future stock model; CC-NEWS if we want raw full text to score ourselves.

### GDELT news-tone TESTED on the macro/ETF basket → robust NULL (2026-06)

We ran the cheap honest test end-to-end (free, no harness). Pulled daily avg `V2Tone` per product
from `gdelt-bq.gdeltv2.gkg_partitioned` (2015–2026, BigQuery sandbox) — first with GKG theme codes,
then **refined to market-specific entities** via `REGEXP_CONTAINS(AllNames, …)` (e.g. `crude oil|OPEC|Brent`
for USO, `gold price|spot gold|bullion` for GLD) to strip non-market framing. Probe = IC of the causal
tone *surprise* (z-score vs trailing 21d) against forward 1/5/20-day returns (Yahoo prices), leak-free.
**Result: robust null.** Refined |IC| ≤ 0.025 at 1 day, **signs flip across horizons** (USO +0.025 1d →
−0.033 20d), sign-hit ~50%. The earlier faint TLT/USO hints (IC ~0.04 on the *impure* themes)
**vanished once the themes were cleaned** → they were artifacts. Cleaner data, weaker "signal" — the
tell of spurious correlation. **Do not pursue GDELT tone as a feature for this macro basket.** Files:
`paper4/news/gdelt_sentiment.py` (BigQuery puller, dry-run + byte cap), `gdelt_tone.csv` (the panel),
`sentiment_probe.py` (the reproducible IC probe). The *stock* route (FNSPID/EDGAR + FinBERT, deeper +
finance-specific) remains **untested** — a separate future question, not refuted by this.

### Future (not built): live/forward news-sentiment overlay + per-source NLP scoring (stocks)

Deferred, gated by the depth limit above. **Two tracks:**

**(A) Live/forward overlay (any universe).** Because deep historical news is unavailable free, a sentiment feature can only run **going forward**, outside the core leak-free backtest: pull a source per product/day → score sentiment with our own LLM (no Finnhub premium `news-sentiment`) → feed as an **11th feature** evaluated live/paper-traded, never retro-fitted. Must pass the parsimony/ablation gate (TA, fundamentals, extra signals all overfit before — see paper4 ablation), so the prior is it is unlikely to beat the bar; an experiment, not a core input. Build as an `ai-trading` add-on, demo-first.

**(B) Per-source NLP → daily score → signal, for a STOCK model (the deep-archive route).** Unlike ETFs/macro, stocks have a deep free archive (FNSPID/EDGAR), so a news signal *can* be backtested leak-free. Plan, source by source (each: text → daily per-ticker sentiment score → standardize → gate/combine like any weak signal, NW-t + DSR + net-of-cost, same harness as `quantiq-pead`/paper4):
  1. **FNSPID** — already news↔price aligned, ~1999–2023: the cleanest backtest substrate. LLM/FinBERT score per article → aggregate to a daily per-ticker sentiment; **point-in-time by article timestamp** (use only news strictly before the trade day).
  2. **EDGAR 8-K** — event-study on official news: classify the 8-K item type + LLM tone → a PiT "disclosure sentiment" around filing date; complements PEAD/SUE.
  3. **GDELT GKG** — pre-computed entity/theme **tone** back to **2015** (no NLP step needed). For our **macro/ETF basket** this is the *primary* historical route (FNSPID is stocks-only); for a stock model it's a second, independent opinion to cross-check FNSPID.
  4. **CC-NEWS** — raw full text, **only if** GDELT shows a real edge and its generic tone proves too coarse to refine (then score with FinBERT). Heaviest; do last, on evidence only.
  **Locked order (cheapest honest test first): GDELT GKG → (only on evidence) CC-NEWS + FinBERT.** Mirrors the fundamentals discipline: cheap test, escalate only if signal appears, report nulls.
  **GDELT access — is BigQuery required?** Not strictly, but it is the practical route for depth. Options: (a) **BigQuery** `gdelt-bq.gdeltv2.gkg` — the easy path: **BigQuery Sandbox is free with NO credit card** (1 TB queries/mo + 10 GB free), the dataset is public, query with SQL; **always filter by `DATE`** (table is many TB — an unfiltered scan burns the 1 TB) and set `maximum_bytes_billed`. Python: `pip install google-cloud-bigquery` + `gcloud auth application-default login` (interactive, run by the user). `V2Tone` is comma-separated; the **first value is the avg tone** → aggregate per theme/entity per day. (b) **Raw GKG CSVs** from `data.gdeltproject.org` (one file / 15 min, free, no account) — same data but you download + parse terabytes locally. (c) the DOC 2.0 API is recent-only (~3 mo) and rate-limits hard (429 from datacenter IPs — confirmed). So depth ⇒ BigQuery (recommended) or bulk CSV.
  Honest expectation: news sentiment is a **weak, decaying, crowded** signal — combine (don't bet alone), expect the edge to shrink net of costs, and report nulls. The value is orthogonality to price-based momentum, not standalone alpha.

### Planned: intraday (1h/4h) deep-momentum project (design basis)

**Chosen architecture basis** (for the new intraday algorithm analogous to paper4):
- **Deep Momentum Networks** (Lim, Zohren, Roberts 2019, arXiv:1904.04912) — an LSTM that outputs the position $X_t\in[-1,1]$ **inside** the volatility-scaling TSMOM framework, trained to **directly maximize Sharpe** (custom loss) with a **turnover-regularization** term; learns trend + sizing jointly. Low-capacity → avoids the overfit the DER paper proved.
- **+ attention via the Momentum Transformer** (Wood, Giegerich, Roberts, Zohren 2022, arXiv:2112.08534) — better regime adaptation than sequential LSTM. PDFs in `Bibliography/intraday-dl-rl-trading/pdfs/`.

**Data source: Yahoo (yfinance).** 1h bars (~730 days of history on Yahoo); **4h is resampled from 1h** (not a native Yahoo interval). Train on Yahoo, serve later on eToro (the paper4 pattern).

**Planned improvements / experiments:** (1) port DMN to 4h; (2) **eToro cost-aware loss** (real spread + overnight financing, not just the paper's 2–3 bps); (3) 1h+4h multi-timeframe fusion; (4) BOCPD changepoint brake (paper4); (5) vol-target as the risk/profit dial; (6) diversified basket incl. crypto (*diversity > count*); (7) quantile/uncertainty sizing (TFT-style).

**First step before building: a cost-survivability probe** — measure the break-even bps of a 4h trend/DMN vs real costs (the whole project arc shows net-of-costs is the killer; paper3 own-PEAD died at 5 bps). If it survives → brainstorm → spec → plan → build.

### paper5 Phase-2 findings (2026-06, free Yahoo + live eToro)

Cost-survivability + regime-stress on a simple vol-targeted TSMOM baseline (no DMN yet — reproduce/critique first):
- **ETF intraday is dead**: 4h gross IR ≈ 0 / negative; break-even ≈ 0.3 bps (1h) — costs annihilate it. **No model fixes turnover.**
- **The no-trade band is the decisive lever**: cuts turnover ~×35 (0.07→0.002) → break-even 5 → **>80 bps**. Mechanism: break-even ≈ gross/turnover, and a direction flip costs **double** (close + open).
- **Crypto banded momentum survives**: 4h break-even >80 bps; **daily** net IR **1.27**, NW-t **2.74**, maxDD **−8%**, and **positive in 2022** (BTC −65%) → not a bull artifact. ETF banded daily also real (net IR 0.57, t=2.30, +in 2022).
- **Live eToro crypto spreads: median ~10 bps** (range 3–32; BTC/ETH ~32) — well under the >80 bps break-even → **survives real costs with margin**.
- **Verdict / direction**: the production-viable core is **crypto (+ETF) banded vol-targeted momentum**; daily is regime-proven, 4h promising but only ~2y of intraday on Yahoo (regime-untestable). The DMN's job is to lift gross edge on this core; deploy daily as the robust base, treat 4h as a live-forward enhancement.

### paper5 Phase-3 findings — DMN build (2026-06, free Yahoo, daily, leak-free nested WF + DSR, net @10bps)

Honest ablation of LSTM DMN + Momentum Transformer vs the fixed-rule banded core. **Diversity is the lever for the ML, not just the rule** — measured, not assumed:
- **Diversification gate (ENB):** the 8-crypto basket has avg |ρ| 0.52 → **ENB 2.6/8** (collapses to ~2.6 real bets, all follow BTC); crypto+ETF 18 has avg |ρ| 0.26 → **ENB 6.1/18**. (`diversification_check.py`, the skill's diversity-gate.)
- **Crypto-only (8, ENB 2.6) = honest null:** LSTM DMN net IR **0.07** (band) → 0.37; Transformer 0.04–0.07 — all **insignificant** (NW-t<1). The thin/redundant universe gives the portfolio-Sharpe loss almost no signal → the network collapses toward zero positions. Fixed-rule wins 1.24 (t=2.73).
- **Combined (18, ENB 6.1) confirms the diagnosis:** LSTM DMN **jumps 0.07 → 0.92** (net IR, NW-t 1.59, DSR 0.86) purely from added diversity — competitive but still **does not beat** the fixed-rule (which falls to 1.11 as ETFs dilute the crypto trend). Honest result: ML revives with diversity but the well-tuned simple rule still wins on free data.
- **Transformer stays data-starved** (0.05–0.07) even diversified: attention needs far more than ~3000 bars; the lower-capacity **LSTM is more sample-efficient** (the DER parsimony thesis again).
- **Hybrid (the real Momentum Transformer: LSTM encoder + pre-LN block-local attention + LR warmup) is WORSE, not better** — net IR **−0.57** (NW-t −1.28, DSR 0.01), vs LSTM 0.92. Stacking attention on the LSTM adds parameters → overfits ~3000 bars → **negative OOS** (fits in-sample noise that inverts). Baselines reproduced exactly (LSTM 0.92, pure-Tr 0.07) so it is not a harness bug. **More capacity hurts on scarce data**; the plain LSTM is the best ML model and the simple rule still wins. (`run_dmn_hybrid.py`, `fig_dmn_hybrid.png`; spec/plan `docs/superpowers/specs|plans/2026-06-07-paper5-hybrid-momentum-transformer*`.)
- **Safe-attention fix (gated residual `h+g·attn`, g init 0; + two-stage frozen-LSTM) prevents the catastrophe but still does not beat the LSTM** — gated-A net IR **0.29**, frozen-B **0.39** (best band), both well under LSTM **0.92**. The gate/freeze stop the −0.57 collapse (no longer negative) but the gate opens on **validation** signal that doesn't generalize OOS on ~3000 bars, and the gated model's own LSTM (different grid; frozen-B's stage-1 gets only epochs//2) is a weaker base — so "floor = 0.92" does NOT hold OOS. **Across all four attention forms (pure 0.07, naive −0.57, gated 0.29, frozen 0.39) attention underperforms the plain LSTM 0.92**: the binding constraint is data (time/regimes), not architecture; diversity (0.07→0.92) was always the real lever. (`run_dmn_gated.py`, `fig_dmn_gated.png`; spec/plan `docs/.../2026-06-07-paper5-gated-hybrid-attention*`.) Next levers: ^VIX regime feature, more uncorrelated assets (ENB), transfer/pretraining on hourly/synthetic (more time).
- **Synthetic-daily pretraining (18 uncorrelated parametric series, warm-start + gate reset) — the honesty control flipped the expected result.** With a single fixed gated cfg: gated-noPT **0.92** (the grid search was actually hurting it; one robust cfg matches the LSTM). **structured-pretrain COLLAPSES to −0.04** (the synthetic taught our assumed dynamics → wrong prior that fine-tuning can't unlearn → the classic "teaches what you bake in" trap, demonstrated). **random-walk-pretrain (signalless) is the BEST result of the whole arc: net IR 1.28** (NW-t 2.20, DSR 1.00) — beats LSTM 0.92, gated-noPT 0.92, and even the fixed-rule 1.11. Pre-registered criterion (genuine attention win = structured>0.92 ∧ structured>randomwalk) **FAILED** (opposite happened) → the gain is **pure regularization/warm-start, NOT learned/transferred structure**; can't attribute 1.28 to attention vs a better-initialized LSTM (final gate not logged). Caveats: **+2022 = no** (the 1.28 lacks crisis durability the fixed-rule has), single seed/cfg (needs replication). Takeaway: signalless pretraining helps as a regularizer; structured-synthetic transfer hurts; the honesty control was decisive. (`run_dmn_pretrain.py`, `fig_dmn_pretrain.png`; spec/plan `docs/.../2026-06-07-paper5-synthetic-pretraining*`.)
- **Multi-seed replication (5 seeds, 2×2+structured) settled both open questions decisively.** (1) **The 1.28 was a lucky seed** — `gated+rwalk` is **0.92 ± 0.43** across seeds (1.28 on seeds 0&2, but 0.11 on seed 3); the true centre is ~0.92, not 1.28. (2) **Attention is irrelevant** — `gated+rwalk` mean **0.92 ± 0.43** equals `LSTM+rwalk` **0.92 ± 0.15** (diff **+0.00**) and **mean|gate| ≈ 0.047** (~closed); attention only adds variance, never signal. (3) **The one genuine, model-agnostic finding: signalless random-walk pretraining is a real REGULARIZER** — it slashes seed variance (LSTM std **0.53→0.15**) and modestly lifts the mean (0.74→0.92) for BOTH LSTM and gated; **structured pretraining hurts** both (LSTM 0.54, gated 0.21 — the bake-in trap, replicated). Net: attention is dead on this data (definitively, via gate-attribution); the LSTM ceiling ~0.92 stays under the rule's 1.11; the deployable nugget is signalless-pretrain-as-variance-reducer for more reliable LSTM-DMN training. (`run_dmn_replicate.py`, `fig_dmn_replicate.png`; spec/plan `docs/.../2026-06-08-paper5-multiseed-replication*`.)
- **Gradient-boosted trees (sklearn HistGradientBoosting, tabular, lower-capacity) are the best ML — they confirm "go simpler, not deeper".** GBT net IR **1.13** (no band) / 0.98 (hard), NW-t 2.16, DSR 0.97 — **beats every deep model** (LSTM 0.92, all attention forms ≤0.92) and **ties the hand-built rule (1.11)**: the first ML to match it. Mechanism is exactly the arc's thesis: thin data rewards strong-inductive-bias / low-capacity models over big nets. **Feature importance (permutation):** the tree leans on **logvol (vol regime) + bocpd (changepoints) + short-horizon returns (ret21/ret1)**; the **3 Kalman-LLT belief features are nearly unused** (kal_tsig **0.000**, kal_innov ~0, kal_vel ~0.002) — the predictive juice is in volatility/regime, not trend-strength belief states (a parsimony hint: the Kalman trend features are redundant here, given vol-normalized returns + logvol). Caveats: **+2022 = no** (GBT, like the LSTM, lacks the rule's crisis durability — the rule stays the only one positive in 2022); the **band HURTS the GBT** (1.13→0.98) since its continuous vol-scaled signal is already smooth (opposite of the choppy sign-rule); single run (GBT is low-variance by design). (`gbt_model.py`, `run_dmn_gbt.py`, `fig_dmn_gbt.png`; spec/plan `docs/.../2026-06-09-paper5-gbt-tabular*`.)
- **eToro REAL-PRICE backtest (read-only candles + real per-asset spreads) — the GBT edge SURVIVES the broker.** `paper5/engine/etoro_gbt_backtest.py` (full leak-free walk-forward on ~1346 real eToro daily candles, 2022-04..2026-06 incl. the 2022 bear, **14/18 assets** resolved — SOL/ADA/DOGE/DBC missing on eToro — with **real per-asset spreads**: BTC/ETH ~31 bps, ETFs 1-4 bps). Net IR (hard band): **fixed-rule 1.52** (NW-t 2.33), **GBT 1.31** (NW-t 2.00, DSR 0.99, **maxDD −3%**), **LSTM 1.00** — all strongly positive, significant, low-drawdown on real broker prices over a window that includes 2022. Hierarchy holds (rule > GBT > LSTM) but **all three work live-price**. Mechanism note: the **band HELPS the GBT here** (0.93→1.31) — opposite of Yahoo (1.13→0.98) — because real crypto spreads (~31 bps) are far above Yahoo's flat 10 bps, so turnover control pays off again (**band value ∝ cost level**). Caveats: backtest not live execution (demo-gated); 14 assets; ~4y only; mixed-calendar ppy~326 approximate; single run. (`fig_etoro_gbt_backtest.png`; spec/plan `docs/.../2026-06-09-paper5-etoro-gbt-backtest*`.) **Actual EUR returns** (`etoro_returns_probe.py`, not just IR): the rule (hard) made **+28.7% over 2.6y = +10.2%/yr** (€10k→€12.9k), GBT +9.6% (€11k) — modest because vol-target 0.15 is low-risk; scale via the vol target. **Diversity-count probe** (`etoro_diversity_probe.py`, rule, same window): **3 assets → ENB 3.0, IR 1.12, maxDD −9%; 5 (SPY/TLT/GLD/BTC/UUP) → ENB 4.5, IR 1.63, +11.6%/yr, maxDD −5% (sweet spot); 14 → ENB 6.5/14, IR 1.61** — "5 uncorrelated > 14 redundant", diversification saturates ~5 well-chosen classes. Greek beginner tutorial of the rule (line-by-line, worked example, real EUR returns, crash behavior, the 3/5/14 experiment, future risk-overlays): `paper5/tutorial_rule_GR.tex/.pdf`.
- **LSTM-improvement levers EXHAUSTED — vol-target sizing does NOT raise the LSTM's profit (`lstm_sizing.py`, `run_lstm_sizing.py`).** Two findings: (1) **LSTM and rule have OPPOSITE basket preferences** — the LSTM is *starved* on the 5-asset sweet spot (raw IR **−0.16**, negative!) because its portfolio-Sharpe loss needs many cross-sectional examples; it needs the **full 18** (raw IR **0.88**, the ~0.92 we knew). The rule prefers 5-diversified (independent per-asset sizing). (2) Applying the rule's **vol-target sizing to the LSTM signal de-risks but kills return**: on combined-18 it cut maxDD −26%→−3% but also ann% 8.7%→~1% and IR 0.88→0.55 — because **the LSTM already learned its own sizing** (Sharpe-loss), so overriding it with inverse-vol + /N just shrinks exposure (realVol 10%→1-4%, far below the 0.15 target). The rule **dominates** combined-18 too (IR **1.14**, ann 7.8%, **maxDD −9%** vs the LSTM's −26% for ~the same return). Verdict: the LSTM ceiling is ~0.88-0.92 on this data; sizing/basket/dial cannot beat the rule. **The real profit lever is the RULE's vol-target dial** (lever up the rule), not the LSTM. (spec/plan `docs/.../2026-06-09-paper5-lstm-voltarget-sizing*`; eToro validation skipped — moot, no improving config.)
- **Model zoo on the paper4 18-ETF universe (`run_etf_zoo.py`) — confirms the UNIVERSE decides which ML wins, reconciling paper4 vs paper5.** Deep Yahoo 2007-2026 (4822 bars, 14 folds, regime-tested: 2008/2020/2022), net @10bps. Net IR (hard): **fixed-rule 0.56** (ann 3.8%), **pure-Transformer 0.53** (ann 4.1% — the BEST ML, nearly ties the rule), GBT 0.43, gated-attn 0.24, **LSTM-DMN 0.02** (dead here). Key: the **pure-Transformer REVIVED 0.07 (crypto) → 0.53 (ETF)** — attention needs subtle trends + diversification + long history (paper4's / the literature's setting); but the **LSTM did NOT revive** (0.92 crypto-combined → −0.12 ETF) — different ML models have different universe sweet spots. The **rule is the only universally-robust model** (best/tied in both universes) though its margin vanishes on ETFs. **Reconciliation:** paper4's modest IRs (rule 0.47, LSTM 0.58) ARE this ETF low-alpha/subtle-trend regime (our rule 0.56 ≈ paper4's 0.47) where ML competes; paper5's high IRs (rule ~1.5) are the crypto high-alpha/obvious-trend regime where the simple rule dominates. So "universe determines the winner" is **confirmed** (esp. for attention), with the rule's universal robustness the other half. (`fig_etf_zoo.png`; spec `docs/.../2026-06-09-paper5-etf-zoo-design.md`.)
- **The band helps the ML too** (LSTM 0.07→0.37 on crypto) — the turnover lever is universal — but cannot rescue a signal-starved model.
- **Weights are NOT saved** in the backtest (correct): a leak-free nested WF has one model per fold, valid only for its test span; evaluation needs only the frozen OOS positions (POS) + returns. Saving a single `model.pt` is a deploy-phase (eToro engine) step, not a backtest step.

## User preferences (durable)

- **No `Co-Authored-By` footer in commit messages**. Use a clean `git commit -m "..."` with no trailer.
- **Non-technical end users are the audience for the product**. Hide complexity behind small public APIs. Don't bolt on defensive code paths "just in case."
- Conversations are Greek/Greeklish; code is English. Mirror what the user uses.
- **Use Opus 4.8 only** — for this main session *and* every dispatched subagent (pass `model: opus` to the Agent tool). Don't downgrade subagents to Sonnet/Haiku.

## Critical conventions

### Secrets

The single source of truth for `MASSIVE_KEY` is `back/.env`. `trader/config.py` reads it from there — **never duplicate the key** into a second `.env`. The repo's `.gitignore` excludes all `.env` files; `back/.env.example` is the committed template.

The key is **lazy**: `config.py` loads `MASSIVE_KEY` at import without raising, and `config.get_massive_key()` raises `RuntimeError` only when something actually needs it (i.e. `source="massive"`). This lets the whole framework run keyless on the default Yahoo source. Don't reintroduce an import-time raise.

`back/.env` is the single store for **all** project secrets: `MASSIVE_KEY`, the eToro keys (`ETORO_PUBLIC_KEY`, `ETORO_PRIVATE_KEY`), `FINNHUB_API_KEY` (earnings estimates/surprises — free tier = last 4 quarters only), `GIT_HUB_TOKEN` (used for pushes), and the Microsoft Graph email creds (`CLIENT_ID`, `CLIENT_SECRET`, `TENANT_ID`, `USER_EMAIL`) used to send mail via Graph `/sendMail` (e.g. `tutorials/send_graph_email.py` — base64 done in-process, creds never printed). Never duplicate or hard-code these elsewhere; `back/.env.example` is the committed template.

### Adding a new strategy

1. Create `trader/strategies/<name>.py`
2. Define a `@dataclass` with the strategy's params (first field can be `tickers: tuple[str, str]` if it's a pair strategy)
3. Subclass `BaseStrategy` and set `name`, `description`, `params_dataclass`, and the backtrader `params` tuple
4. Implement `next()` using `self.datas[i]` and `self.log_trade(...)`
5. That's it — `STRATEGY_REGISTRY` auto-populates on import (metaclass in `trader/strategies/base.py`)

The CLI (`python -m trader strategies`, `backtest`, `sweep`) discovers it automatically; flags are derived from the dataclass via `argparse` introspection in `trader/cli.py::_attach_strategy_flags`.

Don't manually register strategies anywhere. Don't import strategies in `__init__.py` — `pkgutil.iter_modules` does the walk.

### Data layer

`trader/data/loader.py::load_bars` is **cache-aside**: it queries SQLite first (`~/.etoro/cache.db`), fetches only the missing range from the chosen source, upserts, and returns a DataFrame. The cache is keyed `(ticker, timestamp, timespan, source)` — each ticker **and source** stored independently; new tickers/sources extend without disturbing existing ones.

**Two sources, Yahoo is the default.** `load_bars(ticker, start, end, timespan="day", source="yahoo")`. Each provider lives in `trader/data/sources/` and exposes the same `fetch_bars(ticker, start, end, timespan) -> list[dict]`:

- **`yahoo.py`** — free, keyless, adjusted daily bars via `yfinance` (`auto_adjust=True`). `vwap` is always `None`; yfinance's `end` is exclusive so it fetches `end + 1 day`.
- **`massive.py`** — Massive/Polygon REST SDK (`list_aggs`), needs `get_massive_key()`. This is the old `loader.py` fetch logic, extracted.

`loader.py` is **source-agnostic** — it dispatches via `_SOURCES = {"yahoo": yahoo, "massive": massive}` and computes cache gaps **per source**. Adding a third source = drop one `sources/<name>.py` with a `fetch_bars` + register it in `_SOURCES`. An unknown `source` raises `ValueError`.

**Source isolation matters.** Because `source` is in the cache PK, Yahoo and Massive bars for the same ticker never collide (adjusted prices differ slightly between providers). A backtest with no `--source` hits the Yahoo partition; it won't read previously-cached Massive data and will fresh-fetch from Yahoo. That's intentional — pass `--source massive` to reuse Massive data.

**Cache migration is automatic.** `Cache.__init__` detects a pre-multi-source DB (no `source` column) and rebuilds the table once, tagging all existing rows `source='massive'` (everything cached before this feature came from Massive). The `SCHEMA` and `_MIGRATE_ADD_SOURCE` table definitions in `cache.py` must be kept in sync.

**`load_bars` only supports `timespan="day"`**. Intraday raises `NotImplementedError` because gap math currently truncates to dates. Don't lift the guard without redoing the gap calculation in datetime precision.

### `back/` ↔ `trader/` boundary

`trader/` does **not** HTTP-call `back/`. For the Massive source, both import the same `polygon` / `massive` Python SDK directly; for the Yahoo source `trader/` uses `yfinance`. `back/` is Massive-only and for external consumers (future web UI, n8n, etc.) — backtests don't need a server running.

### QUANTIQ web app (`front/` + eToro live layer in `back/`)

The QUANTIQ frontend is a multi-view eToro app for **non-technical** users. It runs against `back/` (demo account, app keys from `back/.env`) on **port 8765**; the Vite dev server proxies `/screener`, `/portfolio`, `/charts`, and `/ws` there (`front/vite.config.ts` — **every backend path the UI calls needs a proxy entry**, or you get `Could not load …`). True multitenant per-user keys (X-User-Id → vault) is a future phase; everything below uses `get_server_client()` (shared app keys).

**Backend pieces (all `get_server_client`, demo):**
- `back/data_cache/etoro_catalog.py` — SQLite cache of the eToro instrument catalog (`~/.etoro/etoro_catalog.db`), populated from `/instruments/discover`. `query`/`all_for_category` (text + `exchange` filter), `exchanges(asset_class)`, `get_by_instrument_ids`. **The eToro REST `fields`/docs are aspirational** — real shapes were reverse-engineered (lean discover items; `/rates` returns bid/ask for only a subset; sector is NOT available).
- `back/routers/screener.py` — `GET /screener/category/{cat}` (paginated/sorted/searched + `exchange` param), `GET /screener/exchanges/{cat}`, `/movers`, `/catalog-status`. A FastAPI lifespan loop auto-refreshes the catalog every ~90s so prices don't freeze.
- `back/etoro_api/ws_client.py` + `back/routers/ws_prices.py` — the **price relay**: ONE shared upstream `wss://ws.etoro.com/ws` connection (`EtoroWsClient`, reconnect/backoff) fanned out to browsers over `GET(ws) /ws/prices`. `PriceRelay` ref-counts instrument subscriptions, computes live change% from prevClose, drops dead clients without breaking fan-out. **The real WS tick frame has NO `type` field and string-typed `Bid/Ask/LastExecution`** — `parse_messages` handles that.
- `back/routers/portfolio.py` — `GET /portfolio/positions` (normalizes `clientPortfolio.positions[]` + enriches symbol/name/seed-rate from the catalog), `POST /portfolio/close/{id}` (demo market-close; `guard_real()` for real, gated by `QUANTIQ_ALLOW_REAL_EXECUTION`).
- `back/routers/chart.py` — `GET /charts/{instrument_id}?interval&count` → normalized OHLCV for the chart. eToro candles are **double-nested** (`data["candles"][0]["candles"]`, newest-first) — flattened to ascending **epoch-ms** candles, incomplete rows dropped, symbol/name enriched from the catalog.

**Frontend (`front/src/`):** `views/ScreenerView.tsx` + `views/PortfolioView.tsx` behind `components/AppNav.tsx`; `App.tsx` is a thin shell. `hooks/usePriceStream.ts` is the browser WS client (reconnect, `Map<id,LiveTick>`); the screener/portfolio overlay live ticks on REST "seed" rows. **Live P&L is computed frontend-side** (`lib/pnl.ts`: `units*(price-open_rate)*(is_buy?1:-1)`) — the same `/ws/prices` relay drives both screener prices and portfolio P&L. The app uses `react-router-dom`: clicking a ticker → `openChart(id)` (`window.open`) opens a new tab at `/chart/:instrumentId` → `views/ChartView.tsx` renders a **KLineCharts** candlestick (`components/Chart.tsx`, canvas; **mocked in tests** since jsdom has no canvas) with timeframe + TA-indicator toolbar and a live last-candle from `/ws/prices`. Each active indicator has a ⚙️ → `components/IndicatorSettingsModal.tsx` (Inputs = `calcParams`, Style = a **swatch palette**, NOT a native `<input type=color>` which pops over the modal); indicators are config objects (`lib/indicators.ts`). **KLineCharts gotcha (cost a debugging session):** the `styles.lines` you pass to `createIndicator`/`overrideIndicator` MUST be **complete** line objects (`{show,size,style,smooth,color,dashedValue}`) — a partial `{color}` silently breaks figure-generation so `indicator.result` stays `undefined` and `drawImp` crashes on **every** redraw (dead mouse/zoom + invisible indicators). Unit tests mock KLineCharts so they can't catch this — verify chart changes live (Playwright/devtools MCP against `npm run dev`). **Naming:** backend API is `/charts` (plural), frontend route is `/chart` (singular) — keep them distinct so the proxy doesn't swallow the route. Tests are fully offline (Vitest + MSW; async backend tests use `asyncio.run`, no `pytest-asyncio`).

**Specs/plans** for all of the above live in `docs/superpowers/specs|plans/2026-06-04-screener-*`, `2026-06-04-portfolio-*`, , `2026-06-05-instrument-chart*`, and `2026-06-05-indicator-settings-modal*`. **Deferred:** sector/industry filter (no cheap data source); WebSocket-true multitenant; chart drawing-tools UI / save layouts; per-indicator persistence (each chart tab starts from defaults).

### Sharpe/Sortino on zero-trade backtests

`extract_metrics` in `trader/engine/analyzers.py` returns `None` for `sharpe`/`sortino` when `total_trades == 0`. Otherwise a flat strategy looks catastrophic. Don't revert this guard.

### `argparse` `from_` workaround

`from` is a Python keyword, so CLI subparsers use `dest="from_"` for the `--from` flag. When extending the CLI, follow the same pattern.

### Windows console

`trader/__main__.py` reconfigures stdout/stderr to UTF-8 on Windows so unicode characters in CLI output don't crash on cp1253 locales. Keep this — it's not redundant.

## Commands

All commands assume cwd is `etoro/`.

### back/ (FastAPI dev server)

```bash
cd back && python -m uvicorn main:app --reload --port 8765
# → http://127.0.0.1:8765/docs
```

### front/ (QUANTIQ web app)

```bash
cd back && python -m uvicorn main:app --reload --port 8765   # backend MUST run first (proxy target)
cd front && npm run dev          # Vite dev server :5173 (proxies /screener,/portfolio,/ws → 8765)
cd front && npm run test:run     # Vitest (offline, MSW)
cd front && npm run build        # tsc -b && vite build
```

`back/` tests for the eToro/QUANTIQ layer: `cd back && python -m pytest tests/ -q` (offline; `test_etoro_*`, `test_screener_*`, `test_price_relay`, `test_ws_prices_endpoint`, `test_portfolio`). If the UI shows `Could not load …` while the screener works, a backend path is missing from the Vite proxy — add it to `front/vite.config.ts` and restart `npm run dev`.

### trader/ tests

```bash
# Full suite with coverage
python -m pytest trader/tests/ -v --cov=trader --cov-report=term-missing

# Single test file
python -m pytest trader/tests/test_cache.py -v

# Single test
python -m pytest trader/tests/test_pair_trading.py::test_hedge_ratio_recovers_known_beta -v

# Skip the smoke test (requires fixtures already present)
python -m pytest trader/tests/ -v --ignore=trader/tests/test_smoke.py
```

Tests are fully offline. Fixtures in `trader/tests/fixtures/*.csv` are UTC-anchored and gitignored by the global rule but committed with `git add -f`.

### trader/ CLI smoke

```bash
python -m trader strategies          # lists auto-registered strategies
python -m trader cache-list          # what's in ~/.etoro/cache.db (shows source per row)
python -m trader fetch AMD --from 2024-01-01 --to today              # Yahoo (default, keyless)
python -m trader fetch AMD --from 2024-01-01 --to today --source massive   # Massive (needs key, ≤2y Basic tier)
```

`--source {yahoo,massive}` (default `yahoo`) is also accepted by `backtest` and `sweep`. `cache-clear` takes an optional `--source` (omit to clear all sources for the ticker).

### Linting / formatting

No linter or formatter is configured. The codebase is plain Python 3.11+ with type hints and `from __future__ import annotations` throughout. Follow existing patterns.

## Architecture notes

### Future (second phase, to design — not built yet): broker-agnostic `quantiq-trading` library + API

The `paper4/engine/` is **already ~90% broker-agnostic** — only `etoro_adapter.py` knows about eToro
(`signal_engine`/`rebalancer`/`sizing`/`features`/`metrics` are pure). The plan for "run on any
platform, not just eToro" is a **refactor, not a rewrite**: extract the engine core into an
installable **`quantiq-trading` package** and make eToro one plugin behind a `BrokerAdapter`
protocol (`search` / `candles` / `positions` / `submit`), registered in a `_BROKERS` dict — exactly
the proven plugin pattern of `trader/data/sources/` (`_SOURCES = {"yahoo","massive"}`, one file per
source). Layering: **library first** (the logic + broker plugins, `pip install quantiq-trading[etoro|all]`,
extras per broker like `agelclaw`), then a thin **FastAPI service** on top (`/signal` `/execute`
`/backtest`, with `broker` as a param), then UI/n8n/3rd-party as consumers. The `ai-trading` skill is
the *methodology*; this library would be the *tool*. **Honest hard 10%:** per-broker symbology,
order model (netting vs hedging, by-amount vs by-units, close-by-positionID vs by-symbol), asset
coverage, fees/financing/market-hours, auth/segments — each new broker needs its own mapping +
offline (mocked) tests. When we pick this up: go brainstorming → spec → plan; decide library/research
boundary (what leaves `paperN/`), the second target broker (Alpaca/IBKR/Binance?), and coexistence
with the existing `trader/` package.

### Layer rule: data → strategies → engine → CLI

`trader/data/` knows about timeseries and SQLite, nothing about strategies. `trader/strategies/` consumes DataFrames and emits backtrader signals — it doesn't fetch. `trader/engine/` orchestrates Cerebro + analyzers. `trader/cli.py` is the entry point. Each layer is independently testable; circular imports are forbidden.

### Sortino is computed manually

`bt.analyzers.SortinoRatio` does **not exist** in backtrader despite the documentation suggesting it does. `trader/engine/analyzers.py::_compute_sortino` computes it from the `TimeReturn` analyzer's daily returns. If you're adding more risk metrics, follow the same pattern (extract from `TimeReturn` rather than trying to use a non-existent built-in).

### Metaclass composition with backtrader

`trader/strategies/base.py::_AutoRegisterMeta` extends `type(bt.Strategy)` — not just `type`. backtrader's `MetaStrategy` does its own subclass machinery; your metaclass MUST inherit from it or `class BaseStrategy(bt.Strategy, metaclass=...)` blows up at class-creation time. The metaclass `__init__` accepts `*args, **kwargs` for forward-compat.

### Strategy auto-discovery is fault-tolerant

`trader/strategies/__init__.py` walks the package with `pkgutil.iter_modules` and wraps each `importlib.import_module` in `try/except` + `warnings.warn`. A broken strategy module doesn't kill the CLI; it just won't appear in the registry. Skip `_`-prefixed modules (helpers).

### Free-tier Massive limits

5 calls/min, ~2 years of history. The cache absorbs both: subsequent backtests on the same range hit zero API calls. When live-testing, prefer date ranges starting within the last 2 years to avoid `NOT_AUTHORIZED` errors.

## Where things live

- Design specs: `docs/superpowers/specs/`
- Implementation plans: `docs/superpowers/plans/`
- Skills used during development: `.Claude/Skills/` (massive-api-skill, etc.)
- Local SQLite cache: `~/.etoro/cache.db` (gitignored)
- Backtest output folders: `results/` (gitignored)
