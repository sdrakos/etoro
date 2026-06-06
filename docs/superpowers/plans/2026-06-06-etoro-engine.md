# eToro Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy the paper4 momentum strategy as a safe CLI engine that computes daily target weights, builds an eToro rebalance plan, optionally executes it on the demo account, and lets an admin retrain/freeze the ML model.

**Architecture:** Six small, bare-import Python modules under `paper4/engine/` (no package machinery — run from that dir, matching the `paper4/code` convention). Pure units (rebalancer, instrument_map, model_store, signal_engine) are fully unit-tested offline; the eToro client is injected and mocked. The CLI wires three commands: `signal` (dry-run), `execute` (demo, gated), `retrain` (admin).

**Tech Stack:** Python 3.11+, numpy, torch, the existing `back/etoro_api` client, the paper4 `code/` + `Strategies/` modules.

**Spec:** `docs/superpowers/specs/2026-06-06-etoro-engine-design.md`

---

## Conventions (read first)

- `paper4/engine/` is **not** a package (no `__init__.py`), like `paper4/code`. Modules import each
  other by bare name. Run the CLI as `python paper4/engine/cli.py <cmd>` (the script's dir is auto
  on `sys.path`). Run tests as `cd paper4/engine && python -m pytest tests -q`.
- Modules that need the paper4 strategy code insert these on `sys.path` at import:
  `paper4/code` and `Strategies/slow-momentum-fast-reversion` (relative to the engine dir).
- The shared order contract (defined in Task 2, reused everywhere):

```python
from dataclasses import dataclass
@dataclass
class Order:
    action: str          # "open" | "close"
    ticker: str
    instrument_id: int
    is_buy: bool         # True=long, False=short
    amount_eur: float    # always positive
    reason: str
```

## File structure

```
paper4/engine/
  rebalancer.py        # (positions, targets) -> [Order]    (pure)
  instrument_map.py    # ticker -> eToro instrumentId       (injected search, cached)
  model_store.py       # save/load frozen LSTM artifact
  signal_engine.py     # fresh prices -> target weights {ticker: w}
  etoro_adapter.py     # thin wrapper over back/etoro_api (positions/candles/submit)
  cli.py               # signal | execute | retrain
  tests/
    test_rebalancer.py
    test_instrument_map.py
    test_model_store.py
    test_signal_engine.py
    test_etoro_adapter.py
```

---

## Task 1: Scaffold

**Files:**
- Create: `paper4/engine/` (directory) and `paper4/engine/tests/` (directory)

- [ ] **Step 1: Create the two directories** (no `__init__.py` — bare-import convention).
On Windows PowerShell: `New-Item -ItemType Directory -Force paper4\engine\tests`.

- [ ] **Step 2: Commit**

```bash
git add paper4/engine
git commit -m "feat(engine): scaffold paper4/engine package dir"
```
(If git won't add an empty dir, defer this commit until Task 2 adds files.)

---

## Task 2: Rebalancer (pure order math)

**Files:**
- Create: `paper4/engine/rebalancer.py`
- Test: `paper4/engine/tests/test_rebalancer.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_rebalancer.py
from rebalancer import Order, plan


def test_open_new_positions_above_threshold():
    targets = {"SPY": 0.5, "TLT": -0.5}             # +long / -short
    imap = {"SPY": 101, "TLT": 102}
    orders = plan([], targets, imap, capital=10000, min_trade=50)
    assert len(orders) == 2
    spy = [o for o in orders if o.ticker == "SPY"][0]
    assert spy.action == "open" and spy.is_buy and abs(spy.amount_eur - 5000) < 1e-6
    tlt = [o for o in orders if o.ticker == "TLT"][0]
    assert tlt.action == "open" and (not tlt.is_buy) and abs(tlt.amount_eur - 5000) < 1e-6


def test_skip_below_min_trade():
    orders = plan([], {"SPY": 0.001}, {"SPY": 101}, capital=10000, min_trade=50)
    assert orders == []                              # 10 EUR < 50 min-trade


def test_close_position_not_in_target():
    current = [{"instrument_id": 101, "is_buy": True, "amount_eur": 3000}]
    orders = plan(current, {"TLT": 1.0}, {"TLT": 102, "SPY": 101}, capital=10000, min_trade=50)
    closed = [o for o in orders if o.action == "close"]
    assert len(closed) == 1 and closed[0].instrument_id == 101


def test_flip_direction_closes_then_opens():
    current = [{"instrument_id": 101, "is_buy": True, "amount_eur": 5000}]
    orders = plan(current, {"SPY": -0.5}, {"SPY": 101}, capital=10000, min_trade=50)
    assert orders[0].action == "close" and orders[0].is_buy
    assert orders[1].action == "open" and (not orders[1].is_buy)


def test_no_action_when_change_below_threshold():
    current = [{"instrument_id": 101, "is_buy": True, "amount_eur": 5000}]
    orders = plan(current, {"SPY": 0.5}, {"SPY": 101}, capital=10000, min_trade=50)
    assert orders == []                              # target 5000 == current 5000
```

- [ ] **Step 2: Run, verify FAIL** — `cd paper4/engine && python -m pytest tests/test_rebalancer.py -q`.

- [ ] **Step 3: Implement**

```python
# paper4/engine/rebalancer.py
"""Pure rebalancing: current eToro positions + target weights -> list of Orders.
Close-and-reopen on a material change (market orders only, this phase); a minimum-trade
threshold suppresses tiny deltas. No IO."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Order:
    action: str          # "open" | "close"
    ticker: str
    instrument_id: int
    is_buy: bool
    amount_eur: float
    reason: str


def _signed(positions):
    """{instrument_id: signed EUR amount} from a list of position dicts."""
    out = {}
    for p in positions:
        amt = float(p["amount_eur"]) * (1.0 if p["is_buy"] else -1.0)
        out[int(p["instrument_id"])] = out.get(int(p["instrument_id"]), 0.0) + amt
    return out


def plan(current_positions, target_weights, instrument_map, capital, min_trade=50.0):
    cur = _signed(current_positions)
    id_to_ticker = {iid: tk for tk, iid in instrument_map.items()}
    orders = []
    target_ids = set()

    for ticker, w in target_weights.items():
        iid = instrument_map.get(ticker)
        if iid is None:
            continue
        iid = int(iid); target_ids.add(iid)
        tgt = w * capital                                  # signed EUR
        have = cur.get(iid, 0.0)
        if abs(tgt - have) < min_trade:
            continue
        if abs(have) > 1e-9:                               # close existing leg first
            orders.append(Order("close", ticker, iid, have > 0, abs(have), "rebalance"))
        if abs(tgt) >= min_trade:
            orders.append(Order("open", ticker, iid, tgt > 0, abs(tgt), "rebalance"))

    for iid, have in cur.items():                          # exit instruments no longer wanted
        if iid not in target_ids and abs(have) >= min_trade:
            tk = id_to_ticker.get(iid, str(iid))
            orders.append(Order("close", tk, iid, have > 0, abs(have), "exit"))
    return orders
```

- [ ] **Step 4: Run, verify PASS** (5 passed).

- [ ] **Step 5: Commit**

```bash
git add paper4/engine/rebalancer.py paper4/engine/tests/test_rebalancer.py
git commit -m "feat(engine): rebalancer (target weights + positions -> orders, min-trade)"
```

---

## Task 3: Instrument map (ticker -> eToro instrumentId)

**Files:**
- Create: `paper4/engine/instrument_map.py`
- Test: `paper4/engine/tests/test_instrument_map.py`

The search function is **injected** so tests never hit the network. The real search (Task 6 wiring)
calls eToro `GET /api/v1/market-data/search?internalSymbolFull=<ticker>`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_instrument_map.py
from instrument_map import resolve, renormalize


def _fake_search(found):
    def search(ticker):
        return found.get(ticker)        # returns instrument_id or None
    return search


def test_resolve_maps_found_skips_missing():
    search = _fake_search({"SPY": 101, "TLT": 102})        # GLD missing
    mp, missing = resolve(["SPY", "TLT", "GLD"], search, override={}, cache={})
    assert mp == {"SPY": 101, "TLT": 102}
    assert missing == ["GLD"]


def test_override_wins_over_search():
    search = _fake_search({"SPY": 101})
    mp, missing = resolve(["SPY"], search, override={"SPY": 999}, cache={})
    assert mp["SPY"] == 999
    assert missing == []


def test_cache_used_without_search():
    calls = []
    def search(t): calls.append(t); return None
    mp, _ = resolve(["SPY"], search, override={}, cache={"SPY": 101})
    assert mp["SPY"] == 101 and calls == []                # cache hit, no search


def test_renormalize_over_available():
    w = {"SPY": 0.5, "TLT": -0.5, "GLD": 0.5}              # gross 1.5
    out = renormalize(w, available=["SPY", "TLT"])         # drop GLD, renormalize gross to 1
    assert set(out) == {"SPY", "TLT"}
    assert abs(sum(abs(v) for v in out.values()) - 1.0) < 1e-9
```

- [ ] **Step 2: Run, verify FAIL.**

- [ ] **Step 3: Implement**

```python
# paper4/engine/instrument_map.py
"""Resolve our ETF tickers to eToro instrument IDs. Order of precedence: manual override >
cache > injected search. Missing tickers are returned separately (caller skips + renormalizes)."""
from __future__ import annotations


def resolve(tickers, search, override=None, cache=None):
    """Return ({ticker: instrument_id}, missing_tickers). `search(ticker)->id|None` is injected."""
    override = override or {}
    cache = cache or {}
    mapping, missing = {}, []
    for tk in tickers:
        if tk in override:
            mapping[tk] = int(override[tk]); continue
        if tk in cache and cache[tk] is not None:
            mapping[tk] = int(cache[tk]); continue
        iid = search(tk)
        if iid is None:
            missing.append(tk)
        else:
            mapping[tk] = int(iid)
    return mapping, missing


def renormalize(weights, available):
    """Keep only `available` tickers and renormalize gross (sum |w|) to 1, signs preserved."""
    kept = {tk: w for tk, w in weights.items() if tk in available}
    gross = sum(abs(w) for w in kept.values())
    if gross < 1e-12:
        return {tk: 0.0 for tk in kept}
    return {tk: w / gross for tk, w in kept.items()}
```

- [ ] **Step 4: Run, verify PASS.**

- [ ] **Step 5: Commit**

```bash
git add paper4/engine/instrument_map.py paper4/engine/tests/test_instrument_map.py
git commit -m "feat(engine): instrument_map (override>cache>search, renormalize over available)"
```

---

## Task 4: Model store (freeze / load the LSTM)

**Files:**
- Create: `paper4/engine/model_store.py`
- Test: `paper4/engine/tests/test_model_store.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_model_store.py
import os, sys, tempfile
import numpy as np
import torch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "code")))
from dmn import DeepMomentumNetwork
from model_store import save, load


def test_save_load_roundtrip_preserves_output():
    net = DeepMomentumNetwork(n_features=10, hidden=8, dropout=0.0).eval()
    mu = np.zeros((1, 1, 10), dtype="float32"); sd = np.ones((1, 1, 10), dtype="float32")
    meta = {"tickers": ["SPY", "TLT"], "lookbacks": [1, 21, 63, 126, 252]}
    x = torch.randn(2, 30, 10)
    with torch.no_grad():
        before = net(x).numpy()
    with tempfile.TemporaryDirectory() as d:
        save(net, mu, sd, meta, name="t", root=d)
        net2, mu2, sd2, meta2 = load("t", root=d)
        with torch.no_grad():
            after = net2(x).numpy()
    assert np.allclose(before, after, atol=1e-6)
    assert np.array_equal(mu, mu2) and np.array_equal(sd, sd2)
    assert meta2["tickers"] == ["SPY", "TLT"]
```

- [ ] **Step 2: Run, verify FAIL.**

- [ ] **Step 3: Implement**

```python
# paper4/engine/model_store.py
"""Save/load the frozen Deep Momentum Network: weights (.pt) + frozen feature scaler (mu/sd) +
meta (universe, lookbacks). Loading reconstructs the net from meta and reuses it for inference."""
from __future__ import annotations
import os, sys, json
import numpy as np
import torch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "code")))
from dmn import DeepMomentumNetwork   # noqa: E402

DEFAULT_ROOT = os.path.expanduser(os.path.join("~", ".etoro", "models"))


def save(net, mu, sd, meta, name, root=DEFAULT_ROOT):
    d = os.path.join(root, name); os.makedirs(d, exist_ok=True)
    torch.save(net.state_dict(), os.path.join(d, "model.pt"))
    np.savez(os.path.join(d, "scaler.npz"), mu=np.asarray(mu), sd=np.asarray(sd))
    full = dict(meta); full["hidden"] = net.lstm.hidden_size
    full["n_features"] = net.lstm.input_size
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(full, f)


def load(name, root=DEFAULT_ROOT):
    d = os.path.join(root, name)
    with open(os.path.join(d, "meta.json"), encoding="utf-8") as f:
        meta = json.load(f)
    net = DeepMomentumNetwork(n_features=meta["n_features"], hidden=meta["hidden"], dropout=0.0)
    net.load_state_dict(torch.load(os.path.join(d, "model.pt"), weights_only=True))  # tensors only
    net.eval()
    z = np.load(os.path.join(d, "scaler.npz"))
    return net, z["mu"], z["sd"], meta
```

- [ ] **Step 4: Run, verify PASS.**

- [ ] **Step 5: Commit**

```bash
git add paper4/engine/model_store.py paper4/engine/tests/test_model_store.py
git commit -m "feat(engine): model_store (freeze/load LSTM + frozen scaler + meta)"
```

---

## Task 5: Signal engine (prices -> target weights) + full-history trainer

**Files:**
- Create: `paper4/engine/signal_engine.py`
- Test: `paper4/engine/tests/test_signal_engine.py`

The price source is **injected** (`fetch_close() -> (close (T,N), tickers)`) so tests are offline.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_signal_engine.py
import os, sys
import numpy as np
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "code")))
from signal_engine import target_weights, train_full


def _fake_fetch(seed=0, T=400, N=4):
    rng = np.random.default_rng(seed)
    close = np.cumprod(1 + rng.normal(0.0003, 0.01, (T, N)), axis=0) * 100
    return close, ["SPY", "TLT", "GLD", "DBC"]


def test_rules_weights_keys_and_gross():
    w = target_weights("rules", fetch_close=lambda: _fake_fetch())
    assert set(w) <= {"SPY", "TLT", "GLD", "DBC"}
    assert sum(abs(v) for v in w.values()) <= 1.0 + 1e-9     # gross <= 1


def test_rules_is_deterministic():
    w1 = target_weights("rules", fetch_close=lambda: _fake_fetch(0))
    w2 = target_weights("rules", fetch_close=lambda: _fake_fetch(0))
    assert w1 == w2


def test_train_full_then_ml_signal(tmp_path):
    close, tickers = _fake_fetch(T=600, N=4)
    train_full(close, tickers, name="t", root=str(tmp_path), epochs=20)
    w = target_weights("ml", fetch_close=lambda: (close, tickers), model_name="t",
                       model_root=str(tmp_path))
    assert set(w) <= set(tickers)
    assert all(-1.0 <= v <= 1.0 for v in w.values())
```

- [ ] **Step 2: Run, verify FAIL.**

- [ ] **Step 3: Implement**

```python
# paper4/engine/signal_engine.py
"""Fresh prices -> target weights {ticker: signed weight}. Rules variant is deterministic and
needs no model; ML variant loads a frozen DMN + scaler and runs inference on the latest bar.
Also provides train_full: train ONE DMN on all history (for the admin `retrain` command)."""
from __future__ import annotations
import os, sys
import numpy as np
import torch

_CODE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "code"))
if _CODE not in sys.path:
    sys.path.insert(0, _CODE)
from features import build_features              # noqa: E402
from ts_momentum import build_ts_weights         # noqa: E402
from dmn import DeepMomentumNetwork, sharpe_loss  # noqa: E402
from model_store import save as _save, load as _load  # noqa: E402


def target_weights(strategy, fetch_close, model_name="prod", model_root=None):
    close, tickers = fetch_close()
    if strategy == "rules":
        W = build_ts_weights(close)
        row = W[-1]
        return {tk: float(row[j]) for j, tk in enumerate(tickers)}
    elif strategy == "ml":
        X, _ = build_features(close)               # (N, T, F)
        kw = {} if model_root is None else {"root": model_root}
        net, mu, sd, _ = _load(model_name, **kw)
        xt = (torch.tensor(X, dtype=torch.float32) - torch.tensor(mu)) / torch.tensor(sd)
        with torch.no_grad():
            pos = net(xt).numpy()                  # (N, T)
        return {tk: float(pos[j, -1]) for j, tk in enumerate(tickers)}
    raise ValueError(f"unknown strategy {strategy!r}")


def train_full(close, tickers, name="prod", root=None, epochs=300, val_frac=0.15):
    """Train ONE DMN on all history with a validation tail for early stopping; freeze + save."""
    X, fwd = build_features(close)
    torch.manual_seed(0)
    T = X.shape[1]; vlo = int(T * (1 - val_frac))
    Xt = torch.tensor(X[:, :T], dtype=torch.float32)
    mu = Xt.mean((0, 1), keepdim=True); sd = Xt.std((0, 1), keepdim=True) + 1e-6
    Xtr = (torch.tensor(X[:, :vlo], dtype=torch.float32) - mu) / sd
    ftr = torch.tensor(fwd[:, :vlo], dtype=torch.float32)
    Xv = (torch.tensor(X[:, vlo:], dtype=torch.float32) - mu) / sd
    fv = torch.tensor(fwd[:, vlo:], dtype=torch.float32)
    net = DeepMomentumNetwork(X.shape[2], hidden=16, dropout=0.0)
    opt = torch.optim.Adam(net.parameters(), lr=1e-3, weight_decay=1e-3)
    best, best_state = float("inf"), None
    for e in range(epochs):
        net.train(); opt.zero_grad(); sharpe_loss(net(Xtr), ftr).backward()
        torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0); opt.step()
        if e % 10 == 0:
            net.eval()
            with torch.no_grad():
                v = float(sharpe_loss(net(Xv), fv))
            if v < best:
                best, best_state = v, {k: val.clone() for k, val in net.state_dict().items()}
    net.load_state_dict(best_state); net.eval()
    meta = {"tickers": list(tickers), "lookbacks": [1, 21, 63, 126, 252]}
    kw = {} if root is None else {"root": root}
    _save(net, mu.numpy(), sd.numpy(), meta, name=name, **kw)
    return name
```

- [ ] **Step 4: Run, verify PASS** (3 passed; the ML test trains a tiny model — a few seconds).

- [ ] **Step 5: Commit**

```bash
git add paper4/engine/signal_engine.py paper4/engine/tests/test_signal_engine.py
git commit -m "feat(engine): signal_engine (rules/ml target weights + full-history trainer)"
```

---

## Task 6: eToro adapter (positions / candles / submit, mocked in tests)

**Files:**
- Create: `paper4/engine/etoro_adapter.py`
- Test: `paper4/engine/tests/test_etoro_adapter.py`

The eToro client is **injected**; tests pass a fake. Real wiring uses
`back.etoro_api.client.get_server_client()` and mirrors `back/routers/portfolio.py` (positions:
`GET /api/v1/trading/info/demo/portfolio` -> `clientPortfolio.positions[]`) and the documented
order endpoint `POST /api/v1/trading/execution/demo/market-open-orders/by-amount`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_etoro_adapter.py
import pytest
from rebalancer import Order
from etoro_adapter import EtoroAdapter


class FakeClient:
    def __init__(self): self.sent = []
    def request(self, method, path, **kw):
        if path.endswith("/portfolio"):
            return {"clientPortfolio": {"positions": [
                {"instrumentID": 101, "isBuy": True, "amount": 3000.0}]}}
        self.sent.append((method, path, kw)); return {"ok": True}


def test_positions_normalized():
    a = EtoroAdapter(FakeClient())
    pos = a.positions()
    assert pos == [{"instrument_id": 101, "is_buy": True, "amount_eur": 3000.0}]


def test_submit_refused_without_execute():
    a = EtoroAdapter(FakeClient(), allow_execute=False)
    with pytest.raises(PermissionError):
        a.submit(Order("open", "SPY", 101, True, 500.0, "rebalance"))


def test_submit_open_sends_request_when_allowed():
    c = FakeClient(); a = EtoroAdapter(c, allow_execute=True)
    a.submit(Order("open", "SPY", 101, True, 500.0, "rebalance"))
    assert len(c.sent) == 1
    method, path, kw = c.sent[0]
    assert method == "POST" and "market-open-orders" in path
```

- [ ] **Step 2: Run, verify FAIL.**

- [ ] **Step 3: Implement**

```python
# paper4/engine/etoro_adapter.py
"""Thin wrapper over the eToro client (injected). Reads/normalizes demo positions, fetches daily
candles, and submits market orders. Execution is refused unless allow_execute=True (demo only,
this phase)."""
from __future__ import annotations

SEG = "demo"   # demo segment only, this phase


class EtoroAdapter:
    def __init__(self, client, allow_execute=False):
        self.client = client
        self.allow_execute = allow_execute

    def positions(self):
        data = self.client.request("GET", f"/api/v1/trading/info/{SEG}/portfolio")
        raw = ((data or {}).get("clientPortfolio") or {}).get("positions") or []
        out = []
        for p in raw:
            iid = p.get("instrumentID")
            if iid is None:
                continue
            out.append({"instrument_id": int(iid), "is_buy": bool(p.get("isBuy")),
                        "amount_eur": float(p.get("amount") or 0.0)})
        return out

    def candles(self, instrument_id, count=500, interval="OneDay"):
        return self.client.request(
            "GET", f"/api/v1/market-data/candles/desc/{instrument_id}/{interval}/{count}")

    def submit(self, order):
        if not self.allow_execute:
            raise PermissionError("execution disabled (pass --execute; demo only)")
        if order.action == "open":
            path = f"/api/v1/trading/execution/{SEG}/market-open-orders/by-amount"
            body = {"instrumentId": order.instrument_id, "isBuy": order.is_buy,
                    "amount": order.amount_eur}
        else:  # close
            path = f"/api/v1/trading/execution/{SEG}/market-close-orders"
            body = {"instrumentId": order.instrument_id}
        return self.client.request("POST", path, json=body)
```

- [ ] **Step 4: Run, verify PASS.**

- [ ] **Step 5: Commit**

```bash
git add paper4/engine/etoro_adapter.py paper4/engine/tests/test_etoro_adapter.py
git commit -m "feat(engine): etoro_adapter (normalized positions/candles/submit, execution gate)"
```

---

## Task 7: CLI (signal / execute / retrain) + data sources

**Files:**
- Create: `paper4/engine/cli.py`

Wires everything. Yahoo source reuses `paper4/code/etf_data.load_etf_matrix`; eToro source builds a
close matrix from `adapter.candles(...)` for the mapped instruments. Real eToro search/client come
from `back/etoro_api`.

- [ ] **Step 1: Implement** (no unit test — this is wiring; verified by smoke run):

```python
# paper4/engine/cli.py
"""eToro engine CLI: signal (dry-run) | execute (demo, gated) | retrain (admin).
Run from repo root: python paper4/engine/cli.py <cmd> [flags]."""
from __future__ import annotations
import os, sys, json, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "code")))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))   # repo root for back.*

from signal_engine import target_weights, train_full   # noqa: E402
from instrument_map import resolve, renormalize         # noqa: E402
from rebalancer import plan                              # noqa: E402
from etoro_adapter import EtoroAdapter                   # noqa: E402

CACHE = os.path.expanduser(os.path.join("~", ".etoro", "instrument_map.json"))


def _yahoo_fetch():
    from etf_data import load_etf_matrix
    close, _dates, tickers = load_etf_matrix()
    return close, tickers


def _load_cache():
    if os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_cache(mp):
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(mp, f)


def _real_client():
    sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "back")))  # so etoro_api.* resolves
    from etoro_api.server import get_server_client   # NB: server.py, not client.py
    return get_server_client()


def _search_fn(client):
    def search(ticker):
        r = client.request("GET", f"/api/v1/market-data/search?internalSymbolFull={ticker}")
        items = (r or {}).get("instruments") or (r or {}).get("data") or []
        return int(items[0]["instrumentId"]) if items else None
    return search


def cmd_signal(args, do_execute=False):
    weights = target_weights(args.strategy, fetch_close=_yahoo_fetch,
                             model_name=args.model)
    client = _real_client()
    mp, missing = resolve(list(weights), _search_fn(client), cache=_load_cache())
    _save_cache(mp)
    if missing:
        print(f"[warn] not on eToro, skipped: {missing}")
    weights = renormalize(weights, available=list(mp))
    adapter = EtoroAdapter(client, allow_execute=do_execute)
    current = adapter.positions()
    orders = plan(current, weights, mp, capital=args.capital, min_trade=args.min_trade)
    print(f"\nStrategy={args.strategy}  capital=EUR{args.capital:,.0f}  orders={len(orders)}")
    for o in orders:
        print(f"  {o.action.upper():<5} {o.ticker:<5} {'LONG' if o.is_buy else 'SHORT':<5} "
              f"EUR {o.amount_eur:>8,.0f}  ({o.reason})")
    if do_execute:
        print("\nExecuting on DEMO...")
        for o in orders:
            try:
                adapter.submit(o); print(f"  ok: {o.action} {o.ticker}")
            except Exception as e:
                print(f"  FAIL {o.action} {o.ticker}: {e}")
    else:
        print("\n(dry-run; pass `execute --execute` to send to demo)")


def cmd_retrain(args):
    close, tickers = _yahoo_fetch()
    print(f"training ML on {close.shape[0]} days x {len(tickers)} assets ...")
    train_full(close, tickers, name=args.model)
    print(f"saved frozen model '{args.model}' to ~/.etoro/models/")


def main():
    ap = argparse.ArgumentParser(prog="paper4-engine")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("signal", "execute"):
        p = sub.add_parser(name)
        p.add_argument("--strategy", choices=["rules", "ml"], default="rules")
        p.add_argument("--capital", type=float, default=10000.0)
        p.add_argument("--min-trade", type=float, default=50.0)
        p.add_argument("--model", default="prod")
        if name == "execute":
            p.add_argument("--execute", action="store_true")
    pr = sub.add_parser("retrain"); pr.add_argument("--model", default="prod")
    args = ap.parse_args()
    if args.cmd == "signal":
        cmd_signal(args, do_execute=False)
    elif args.cmd == "execute":
        cmd_signal(args, do_execute=args.execute)
    elif args.cmd == "retrain":
        cmd_retrain(args)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke — argparse + dry-run wiring without network.**
Run: `python paper4/engine/cli.py --help` then `python paper4/engine/cli.py signal --help`.
Expected: usage prints with `signal`, `execute`, `retrain` and the flags. (A full `signal` run hits
live eToro + Yahoo; do that manually when ready, demo only.)

- [ ] **Step 3: Commit**

```bash
git add paper4/engine/cli.py
git commit -m "feat(engine): CLI (signal/execute/retrain) wiring Yahoo+eToro, demo-gated"
```

---

## Task 8: Full suite + README

**Files:**
- Create: `paper4/engine/README.md`

- [ ] **Step 1: Run the whole engine suite**
Run: `cd paper4/engine && python -m pytest tests -q`
Expected: all tests pass (rebalancer 5, instrument_map 4, model_store 1, signal_engine 3,
etoro_adapter 3).

- [ ] **Step 2: Write `paper4/engine/README.md`** documenting the three commands, the
demo-only/`--execute` safety, the Yahoo-train / eToro-signal split, and the instrument-map
override file. (Prose; mirror the spec's summary.)

- [ ] **Step 3: Commit**

```bash
git add paper4/engine/README.md
git commit -m "docs(engine): README (commands, safety, train/serve split)"
```

---

## Self-review notes

- **Spec coverage:** §2 commands → Tasks 5,7 (signal/execute/retrain). §3 components → rebalancer
  (T2), instrument_map (T3), model_store (T4), signal_engine+trainer (T5), etoro_adapter (T6), cli
  (T7). §4 data flow → T7. §5 train/serve split → T5 (`train_full` on Yahoo) + T7 (`--source`,
  see note). §6 safety → T6 gate + T2 min-trade + T3 skip-warn. §7 testing → mocked client
  throughout. §8 layout → matches.
- **`--source etoro` note:** the CLI in T7 ships the Yahoo source wired; the eToro candle source is
  a thin follow-up (build a close matrix from `adapter.candles` for the mapped instruments and pass
  it as `fetch_close`). It is intentionally a small, isolated addition so the first deliverable is
  testable end-to-end on the deep Yahoo data; flag `--source` is reserved in the parser when added.
- **Type consistency:** `Order` fields identical across T2/T6/T7. `target_weights(strategy,
  fetch_close, model_name, ...)`, `resolve(tickers, search, override, cache)`, `renormalize(weights,
  available)`, `plan(current, target, instrument_map, capital, min_trade)`, `EtoroAdapter(client,
  allow_execute)` consistent across tasks.
- **Real eToro endpoint paths** (positions/orders/search) are taken from `back/routers/portfolio.py`
  and the etoro-api skill; since the adapter is mocked in tests, confirm the exact live paths
  against those references when first running `execute` on demo.
```
