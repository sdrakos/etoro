# eToro deployment engine

How a model goes from a backtest to live orders on eToro. Mirror `paper4/engine/`; the API shapes
below were reverse-engineered (the official docs are aspirational). The richer `etoro-api` skill
covers the full client — this file is the **engine** layer on top of it.

## Architecture (signal → weights → mapping → plan → execute)

| module | role |
|--------|------|
| `signal_engine.py` | fresh prices → target weights (`rules` deterministic, `ml` frozen-DMN inference); `train_full` for retrain |
| `instrument_map.py` | resolve tickers → eToro instrument IDs (override > cache > live search) and **renormalize** the book over the available subset |
| `model_store.py` | save/load the frozen model (`torch.load(..., weights_only=True)`) under `~/.etoro/models/<name>/` |
| `rebalancer.py` | pure plan builder: current positions + target weights → `Order`s, with min-trade suppression. No IO. `Order` carries `position_id` for closes |
| `etoro_adapter.py` | thin client wrapper: read demo positions, fetch candles, submit market orders (gated by `allow_execute`) |
| `cli.py` | wiring: `signal` (dry-run) / `execute` (demo, gated) / `retrain` |
| `etoro_backtest.py` | backtest on **real eToro daily candles** (~4y) for a chosen product set |

## CLI surface

```bash
python paper4/engine/cli.py signal  [--strategy rules|ml] [--capital 10000] [--min-trade 50] \
                                    [--target-vol 0.10] [--vol-method rolling|ewma] [--model prod]
python paper4/engine/cli.py execute [--execute]   # same plan; --execute sends to DEMO only
python paper4/engine/cli.py retrain [--model prod] # admin: train + freeze the ML model
python paper4/engine/etoro_backtest.py SPY TLT GLD USO UUP --long-only --vol 0.20 [--vol-method rolling|ewma] [--compare-vol]
```

## Exact eToro endpoints (verbatim from our code — `SEG = "demo"` this phase)

All paths carry the **`/api/v1/`** prefix and the segment `{SEG}` (`demo` now; `real` only when
real execution is unlocked). These are the reverse-engineered shapes our engine actually calls:

| Action | Method + path | Response shape / notes |
|--------|---------------|------------------------|
| Instrument search | `GET /api/v1/market-data/search?internalSymbolFull={TICKER}` | matches under **`items[]`** (NOT `instruments`/`data`); filter exact `internalSymbolFull`, drop `isHiddenFromClient`. 17/18 ETFs resolve (DBC missing; BTC ok) |
| Daily candles | `GET /api/v1/market-data/instruments/{id}/history/candles/desc/{interval}/{count}` (e.g. `.../desc/OneDay/1000`) | **double-nested**: `data["candles"][0]["candles"]`, newest-first → flatten ascending, drop incomplete rows. ~1000 daily bars (~4y) |
| Live rates | `GET /api/v1/market-data/instruments/rates` | bid/ask for a subset only |
| Instrument metadata | `GET /api/v1/market-data/instruments` | lean discover items (sector NOT available) |
| Portfolio / positions | `GET /api/v1/trading/info/{SEG}/portfolio` | positions under **`clientPortfolio.positions[]`** → normalize to `{instrument_id, is_buy, amount_eur, position_id}` |
| Account PnL | `GET /api/v1/trading/info/{SEG}/pnl` | |
| **Open** (by amount) | `POST /api/v1/trading/execution/{SEG}/market-open-orders/by-amount` | gated by `allow_execute` |
| **Close** (by positionID) | `POST /api/v1/trading/execution/{SEG}/market-close-orders/positions/{positionId}` | NOT by instrument — a 404 means you closed by the wrong key. Plumb `position_id` from read positions → `rebalancer.Order` → adapter |

The **server client** is `from etoro_api.server import get_server_client` (add `back/` to `sys.path`;
`server.py` internally does `from etoro_api.client import ...`). Shared app keys = demo. The full
typed client + the docs MCP live behind the **`etoro-api`** skill — consult it for anything beyond
these engine endpoints.

## Volatility targeting in the engine (the risk dial)

- `_vol_target_capital(close, tickers, weights, capital, target_vol, method)` estimates the book's
  **recent** vol from the current weights on a **trailing** window (`rolling` ≈ 63d equal-weight, or
  `ewma` ≈ 126d recency-weighted via `sizing.realized_vol`), then levers `clip(target/bookvol, 0.2, 3)`.
- **Causal** — re-estimated every run from the latest window, no look-ahead. This is the correct live
  behavior; the backtest's optional `static` (whole-period) mode is illustration-only.
- On real eToro prices the causal `rolling` was not a cost — it slightly beat `static` (same drawdown).
- Expose `--vol-method` so the **front-end** can offer the choice (rolling = steady, ewma = reacts faster).

## Safety gating (mandatory)

- Default path is **dry-run, signal-only** — nothing is sent.
- Execution is **demo only** and requires the explicit `--execute` flag; the adapter refuses unless
  `allow_execute=True`. Real money is gated behind `QUANTIQ_ALLOW_REAL_EXECUTION` and needs the
  user's explicit, in-context go-ahead. This is **not** an auto-trader.
- A **min-trade threshold** suppresses tiny orders.
- **Idempotency caveat:** positions just opened are *pending*; re-running `execute` before they fill
  double-submits. Before going beyond manual demo runs, add pending-order/market-hours guards.

## Tests

Fully offline — the eToro client is mocked (`paper4/engine/tests/`, run from the `engine/` dir).
`parse_candles`/`build_closes`/`backtest_rules` (incl. causal `_trailing_vol`) are pure-tested;
the live `run()` hits the demo client. Keep this suite green before any deploy.
