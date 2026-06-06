# eToro Engine — design (paper4 strategy → live/demo deployment)

**Date:** 2026-06-06
**Status:** design — approved, pending spec review
**Author:** Stefanos Drakos / AGEL AI
**Home:** `etoro/paper4/engine/` (CLI now; thin FastAPI wrapper in `back/` later)

---

## 1. Goal

Turn the paper4 diversified-momentum strategy into a deployable engine that (a) computes daily
target weights, (b) reconciles them against the live eToro portfolio into a concrete rebalance
plan, and (c) optionally executes that plan on the **demo** account. Plus an **admin retrain**
command that freezes a fresh ML model. Safe by default: dry-run signal-only unless explicitly told
to execute, and never real money in this phase.

## 2. Commands (CLI: `python -m paper4.engine <cmd>`)

| Command | What it does | Executes? |
|---|---|---|
| `signal` | Compute target weights (rules/ML), read current eToro portfolio, print the rebalance plan (orders needed). | No (dry-run) |
| `execute [--execute]` | Same, and **send orders to the demo account** when `--execute` is passed; without it, dry-run. | Demo only, gated |
| `retrain` | **Admin:** train the ML on all Yahoo history to today → freeze → save artifact. | No |

Flags: `--strategy rules|ml` (default `rules`), `--source yahoo|etoro` (default `yahoo`),
`--capital <eur>`, `--execute`, `--min-trade <eur>`.

## 3. Components (6 small, independently testable units)

### `instrument_map.py`
Resolve our ETF tickers → eToro `instrumentId` via `/instruments/search`. Cache the mapping to
`~/.etoro/instrument_map.json`. Support a manual override file. Tickers not found on eToro are
**skipped with a warning**; the book's weights are **renormalized over the available subset**.
Interface: `resolve(tickers) -> {ticker: instrument_id}`, `available(tickers) -> list[str]`.

### `model_store.py`
Save/load the frozen ML artifact: the trained LSTM weights (`model.pt`) plus the frozen feature
standardization (mean/std) and the universe/feature config, under `~/.etoro/models/<name>/`.
Interface: `save(model, scaler, meta, name)`, `load(name) -> (model, scaler, meta)`.

### `signal_engine.py`
Pure: fresh price data → target weights. Reuses the paper4 code unchanged
(`features.build_features`, `ts_momentum.build_ts_weights`, `dmn` inference). Data source is
injected: `source="yahoo"` (deep history) or `source="etoro"` (production — last ~500 daily
candles per instrument). For `ml`, applies the frozen model + frozen scaler from `model_store`.
Interface: `target_weights(strategy, source, asof) -> {ticker: weight}`.

### `rebalancer.py`
Pure: `(current_positions, target_weights, capital, min_trade)` → ordered list of orders
(close / open / adjust), with a **minimum-trade threshold** so tiny deltas don't spam orders.
Dollar-neutral/directional aware. Interface: `plan(current, target, capital, min_trade) -> [Order]`.

### `etoro_adapter.py`
Thin wrapper over the existing `back/etoro_api` client (`get_server_client`, demo): read
positions, fetch daily candles (for `source=etoro`), place/close market orders. Execution is
**gated**: refuses unless `--execute` AND `QUANTIQ_ALLOW_REAL_EXECUTION` semantics keep real off
(demo only this phase). Interface: `positions()`, `candles(instrument_id, count)`, `submit(order)`.

### `cli.py`
Wires the three commands and flags; prints the plan as a readable table; on `--execute` calls the
adapter per order and reports results.

## 4. Data flow

```
retrain:  Yahoo (deep) -> features -> train LSTM -> freeze -> model_store
signal/execute:
  signal_engine(strategy, source) ──► target weights {ticker: w}
        │ (source=etoro: candles via etoro_adapter; source=yahoo: trader/data)
        ▼
  instrument_map  ──► {instrument_id: w}   (skip+warn missing, renormalize)
        ▼
  etoro_adapter.positions()  +  rebalancer.plan()  ──► [orders]
        ▼
  dry-run print   OR   etoro_adapter.submit() per order (demo, gated)
```

## 5. Train / serve split (honest)

- **Training is always on Yahoo** (needs ~17 years; eToro candles are too shallow to train).
- **Live signal may use eToro** (`--source etoro`): the rolling features need ≤252 days of lookback,
  which the eToro daily candle history (~1000 bars) covers. This makes the production signal
  self-consistent with the instruments actually traded.
- **Train/serve skew:** Yahoo and eToro prices differ slightly (adjustments, CFD wrapping). The
  features are volatility-normalized returns (largely scale-invariant), which mitigates this, but
  it is a documented caveat; the frozen scaler is from Yahoo training.

## 6. Safety (first-class)

- Default is **dry-run signal-only**. Execution requires the explicit `--execute` flag.
- Execution targets the **demo** account only in this phase; real stays gated behind
  `QUANTIQ_ALLOW_REAL_EXECUTION` (off). Real-money execution is out of scope.
- **Minimum-trade threshold** prevents micro-order spam.
- Missing instruments are skipped with a warning, never silently mis-mapped.

## 7. Testing

Fully offline; the live eToro client is **mocked**. Cases:
- `instrument_map`: skip+warn for a missing ticker, weight renormalization, manual override wins.
- `rebalancer`: order math (close/open/adjust), min-trade threshold drops tiny deltas, gross sanity.
- `model_store`: save→load round-trip preserves inference output.
- `signal_engine`: deterministic shape/keys on a synthetic price feed; rules vs ml selectable.
- `etoro_adapter`: execution refused without `--execute`; orders built correctly (against a mock).

No live eToro calls in tests.

## 8. File layout

```
paper4/engine/
  __init__.py
  instrument_map.py
  model_store.py
  signal_engine.py
  rebalancer.py
  etoro_adapter.py
  cli.py            # python -m paper4.engine
  tests/
    test_instrument_map.py
    test_rebalancer.py
    test_model_store.py
    test_signal_engine.py
    test_etoro_adapter.py
```

## 9. Out of scope (YAGNI)

Real-money execution; a built-in scheduler/cron (run manually or via an external scheduler);
the FastAPI wrapper (a later, thin phase); multitenant per-user keys; partial fills / advanced
order types (market orders only this phase).

## 10. Production note

In production the data source is `--source etoro` (signals on the actual traded instruments) and
execution is on eToro demo first; promotion to real is a separate, later decision gated by a long
demo paper-trading track record.
