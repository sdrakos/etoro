# paper4 eToro engine

Deploys the **paper4 diversified-momentum** strategy to eToro. It turns a signal into a
**rebalance plan** against your current eToro portfolio, and can optionally send the
resulting orders to the **demo** account. An admin command retrains the ML model.

The flow is: **signal → target weights → instrument mapping → rebalance plan → (optional) demo execution.**

## Commands

Run from the repo root (`etoro/`).

### `signal` — compute the plan (dry-run, never executes)
```bash
python paper4/engine/cli.py signal [--strategy rules|ml] [--capital 10000] [--min-trade 50] [--model prod]
```
Computes target weights, resolves tickers to eToro instrument IDs, reads your current eToro
portfolio, and prints the rebalance plan. **No orders are sent.**

### `execute` — same plan, optional demo execution
```bash
python paper4/engine/cli.py execute [--execute] [--strategy rules|ml] [--capital 10000] [--min-trade 50] [--model prod]
```
Identical to `signal`, but when `--execute` is passed it submits the orders to the **demo**
account. Without `--execute` it is a dry-run.

### `retrain` — admin: train and freeze the ML model
```bash
python paper4/engine/cli.py retrain [--model prod]
```
Trains the Deep Momentum Network on the full Yahoo history, freezes it (weights + feature
scaler + meta), and saves it to `~/.etoro/models/<model>/`.

**Flags**

| flag | default | meaning |
|------|---------|---------|
| `--strategy` | `rules` | `rules` (deterministic TS-momentum, no model) or `ml` (frozen DMN inference) |
| `--capital`  | `10000` | gross book size in EUR the weights are scaled to |
| `--min-trade`| `50`    | suppress any order whose EUR delta is below this threshold |
| `--model`    | `prod`  | named model under `~/.etoro/models/` (used by `ml` and `retrain`) |
| `--execute`  | off     | (`execute` only) actually send orders to the **demo** account |

## Safety

- The default path is **dry-run, signal-only** — nothing is sent anywhere.
- Execution is **demo only** this phase, and requires the explicit `--execute` flag.
  The adapter refuses to submit unless `allow_execute=True`.
- A **minimum-trade threshold** (`--min-trade`) suppresses tiny orders.
- **Real-money execution is out of scope this phase.** This is not an auto-trader.

## Train / serve split

Training is **always on Yahoo** (deep, free history) — both `rules` weights and the `ml`
model derive from Yahoo bars. At serve time the live signal can run on Yahoo (dev) or on
eToro candles (production, self-consistent with the instruments you actually trade). There
is a mild **Yahoo↔eToro train/serve skew** (adjusted prices differ slightly between
providers); it is mitigated by the vol-normalized features the model consumes.

## Instrument mapping

Tickers are auto-resolved to eToro instrument IDs via `/market-data/search` and cached to
`~/.etoro/instrument_map.json` (manual override > cache > live search). ETFs that are **not
listed on eToro** are skipped with a warning, and the book is **renormalized over the
available subset** (gross exposure back to 1), so the plan stays fully invested in what can
actually be traded.

## Modules

| module | role |
|--------|------|
| `rebalancer.py`     | pure plan builder: current positions + target weights → list of `Order`s, with min-trade suppression. No IO. |
| `instrument_map.py` | resolve tickers → eToro instrument IDs (override/cache/search) and renormalize the book over the available subset. |
| `model_store.py`    | save/load the frozen Deep Momentum Network (weights + scaler + meta) under `~/.etoro/models/`. |
| `signal_engine.py`  | fresh prices → target weights (`rules` deterministic, `ml` DMN inference); also `train_full` for `retrain`. |
| `etoro_adapter.py`  | thin wrapper over the eToro client: read demo positions, fetch candles, submit market orders (gated by `allow_execute`). |
| `cli.py`            | wiring: the `signal` / `execute` / `retrain` commands. |

## Tests

```bash
cd paper4/engine && python -m pytest tests -q
```
16 tests, fully offline (the eToro client is mocked): rebalancer 5, instrument_map 4,
model_store 1, signal_engine 3, etoro_adapter 3.

## Status

The signal engine is **built and tested**. Live `signal` / `execute` against the eToro
**demo** account should be exercised manually before any real use — **demo-first**.
