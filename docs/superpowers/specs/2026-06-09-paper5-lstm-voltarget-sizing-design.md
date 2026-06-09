# paper5 LSTM + volatility-target sizing (increase profit) — Design

**Date:** 2026-06-09
**Status:** Approved (brainstorming), ready for implementation plan
**Owner:** Stefanos
**Pipeline:** `ai-trading` skill — phase 3 (evolve): give the LSTM the rule's proven sizing.

## 1. Goal & scope

The LSTM-DMN (net IR ~0.92 Yahoo / 1.00 eToro) loses to the fixed rule (1.52 eToro). Its two gaps vs
the rule: (a) it has **no explicit volatility-target sizing** (it emits raw `tanh` positions), and (b)
it ran on the **14 redundant** assets instead of the **5 diversified** sweet spot (ENB 4.5 vs 6.5/14).
This iteration closes both — **the LSTM picks direction/conviction, the rule's sizing weights it** — to
raise the LSTM's risk-adjusted and absolute profit using only the data we have. No retraining (a
serving-time sizing wrapper); no new model capacity (which we proved overfits).

> Does volatility-target sizing on the LSTM signal, on the 5-asset sweet spot, raise its IR (and
> profit at matched risk) toward the rule?

**In scope:** a `size_positions` sizing wrapper; a Yahoo-deep 5-asset sweep of `target_vol`
(0.10/0.15/0.30) comparing raw-LSTM / sized-LSTM / rule; the best config validated on real eToro
prices; offline tests.

**Out of scope (future):** signalless-pretrain regularization, LSTM+rule ensemble, BOCPD brake, the
paper5_rule project, the journal paper.

## 2. Locked decisions (from brainstorming)

- **Sizing wrapper:** `position = clip(LSTM_tanh * (target_vol / vol), +/-2)` then per-asset `ewm(5)`;
  the no-trade band is applied downstream by `evaluate` (as for every model). The LSTM's continuous
  conviction (not just its sign) is kept and re-scaled by inverse vol.
- **Universe:** the diversified 5-asset sweet spot **SPY, TLT, GLD, BTC-USD, UUP** (equities, bonds,
  gold, crypto, dollar) — subset of the combined-18 panel.
- **Dial sweep:** `target_vol in {0.10, 0.15, 0.30}` — the profit/risk knob.
- **Eval surface:** Yahoo 5-asset deep (regime-tested, incl. 2022) for the sweep; the best config then
  validated on real eToro prices (real per-asset spreads).
- **Criterion:** risk-adjusted — does sizing raise the **IR** vs raw-LSTM; plus report **realized
  annualized vol** per variant so profit can be read **at matched risk** (the dial frontier). No tuning
  to force a win.

## 3. Architecture

No retraining and no change to the torch training functions — a serving-time wrapper + drivers.
paper4 untouched.

```
paper5/code/
  lstm_sizing.py        # size_positions(POS, vol, target_vol, clip, ewm_span) -> sized POS (N,T)
  run_lstm_sizing.py    # Yahoo 5-asset deep: LSTM nested-WF once -> sweep sizings vs rule (table+figure)
  tests/                # test_lstm_sizing.py
paper5/engine/
  (extend etoro_gbt_backtest reuse) — best sized-LSTM config validated on real eToro prices
```

Reuse: `crypto_features.build`, `train_eval.{make_folds, nested_walkforward, evaluate}`,
`models.make_lstm`/`LSTM_GRID`, `band_eval`, `combined_data.fetch_combined_daily` (subset 5),
`metrics.{ann_ir, newey_west_t, max_drawdown}`, and (for eToro) the `etoro_gbt_backtest` helpers.

## 4. The sizing wrapper (`lstm_sizing.py`)

```python
def size_positions(POS, vol, target_vol=0.15, clip=2.0, ewm_span=5):
    """POS (N,T) raw LSTM tanh positions; vol (N,T) causal annualized realized vol.
    Returns vol-targeted positions (N,T): clip(POS * target_vol/vol, +/-clip), then per-asset EWM."""
    import pandas as pd
    sized = np.clip(np.asarray(POS, float) * (target_vol / np.maximum(vol, 1e-6)), -clip, clip)
    return pd.DataFrame(sized.T).ewm(span=ewm_span, min_periods=1).mean().to_numpy().T
```

Flow: run `nested_walkforward(make_lstm, LSTM_GRID, X, fwd, folds)` ONCE -> `POS_lstm (N,T)` + `test_idx`.
For each variant apply a sizing, then `evaluate` (which applies band + /N + costs):
- `raw`: `POS_lstm` unchanged (the current ~0.92 behavior).
- `vt{0.10,0.15,0.30}`: `size_positions(POS_lstm, vol, target_vol)`.
`vol (N,T)` is the causal annualized realized vol from the 5-asset close (`ret.rolling(30).std()*sqrt(ppy)`,
shifted 1). The fixed rule is computed on the same 5-asset panel as the reference row.

## 5. Sweep, comparison, eToro validation

Yahoo 5-asset deep, leak-free nested WF, net @10bps, hard band, DSR `n_trials=len(LSTM_GRID)`. The
driver `run_lstm_sizing.py` prints:

| variant | net IR | ann % | maxDD | realized vol |
|---------|--------|-------|-------|--------------|
| LSTM raw | ... | ... | ... | ... |
| LSTM + vt 0.10 | ... | ... | ... | ... |
| LSTM + vt 0.15 | ... | ... | ... | ... |
| LSTM + vt 0.30 | ... | ... | ... | ... |
| fixed-rule | ... | ... | ... | ... |

`realized vol` = annualized std of the variant's net stream -> lets us read profit **at matched
risk**. `ann %` = annualized return from the net stream (`prod(1+net)^(ppy/n)-1`). Save
`figures/fig_lstm_sizing.png` (IR + ann% bars, with the rule reference). **Then** the best
`target_vol` config is run on real eToro prices (5-asset, real per-asset spreads) via the
`etoro_gbt_backtest` helpers, reported next to the rule and GBT.

**Success:** sized-LSTM IR clearly > raw-LSTM (~0.92); report by how much, and the profit gained per
unit risk from the dial. Reaching/beating the rule (1.5+) is a bonus. Honest result either way.

## 6. Testing (offline, no network, no training)

- `test_lstm_sizing.py`:
  - **zero target_vol -> zero position**: `size_positions(POS, vol, target_vol=0.0)` is all ~0.
  - **inverse vol**: doubling `vol` halves the (pre-clip) position for the same `POS`/`target_vol`.
  - **clip**: a huge `POS/vol` is capped at `|2|`; shape stays `(N,T)`; output finite.
  - **smoothing**: a step input is smoothed (the EWM of a jump is below the jump on the first step).
- Heavy LSTM training and the eToro validation run only in the drivers.

## 7. Conventions

- Serving-time wrapper; the torch `train_eval` training functions and `paper4/` are untouched.
- Yahoo via `combined_data` cache; eToro read-only (candles/rates). No `Co-Authored-By`. Opus for any
  dispatched subagent. Code/figures English, commentary Greek. Figures `git add -f`. `random_state`/
  `torch.manual_seed(0)` already set in the reused code. Honest: increasing `target_vol` raises both
  return and drawdown ~linearly — the comparison is at matched risk, not raw return.
