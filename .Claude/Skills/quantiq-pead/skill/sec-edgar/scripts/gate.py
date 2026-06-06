#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gate.py — decide which signals actually carry durable, tradable direction.

The lesson from Jane Street's Kaggle setup: score by ECONOMIC UTILITY (weight x return),
not by accuracy. So each signal is judged by the risk-adjusted P&L of its own long-short
portfolio (which is utility-weighted by construction), with Newey-West inference and an
early-vs-late split to flag nonstationarity (decay).

A signal PASSES if its out-of-sample utility is positive and statistically real
(|NW t| >= t_thresh) and not collapsing across time.
"""

import numpy as np
import pandas as pd


def _zscore_xs(frame):
    mu = frame.mean(axis=1)
    sd = frame.std(axis=1).replace(0, np.nan)
    return frame.sub(mu, axis=0).div(sd, axis=0).fillna(0.0)


def _nw_t(x, L):
    x = np.asarray(x, float); x = x[np.isfinite(x)]; n = len(x)
    if n < 5:
        return 0.0
    xm = x - x.mean(); var = (xm @ xm) / n
    for k in range(1, min(L, n-1)+1):
        var += 2*(1-k/(L+1))*((xm[k:] @ xm[:-k])/n)
    se = np.sqrt(max(var, 1e-18)/n)
    return float(x.mean()/se) if se > 0 else 0.0


def signal_pnl(signal, ret):
    """Utility-weighted long-short daily P&L of one signal: weight=z-score, dollar-neutral,
    earn NEXT day's return (weight x return = the economic utility, JS-style)."""
    z = _zscore_xs(signal)
    c = z.columns.intersection(ret.columns)
    z = z[c]; r = ret[c].reindex(z.index)
    w = z.div(z.abs().sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
    return (w.shift(1) * r).sum(axis=1)


def rank_ic(signal, ret):
    """Mean daily cross-sectional rank correlation between signal and next-day return."""
    z = signal.rank(axis=1)
    r = ret.shift(-1).rank(axis=1)
    c = z.columns.intersection(r.columns)
    ic = z[c].corrwith(r[c], axis=1)
    return float(ic.mean()), ic.dropna()


def evaluate_signal(signal, ret, L=20):
    p = signal_pnl(signal, ret).dropna()
    if len(p) < 60:
        return dict(IR=0.0, t_NW=0.0, mean_IC=0.0, IR_early=0.0, IR_late=0.0, n=len(p))
    ir = float(np.sqrt(252)*p.mean()/(p.std()+1e-12))
    t = _nw_t(p.values, L)
    mic, _ = rank_ic(signal, ret)
    half = len(p)//2
    e, l = p.iloc[:half], p.iloc[half:]
    ir_e = float(np.sqrt(252)*e.mean()/(e.std()+1e-12))
    ir_l = float(np.sqrt(252)*l.mean()/(l.std()+1e-12))
    return dict(IR=round(ir, 3), t_NW=round(t, 2), mean_IC=round(mic, 4),
                IR_early=round(ir_e, 3), IR_late=round(ir_l, 3), n=int(len(p)))


def gate(signals, ret, t_thresh=2.0, L=20):
    """
    Evaluate a dict of signal frames. Returns (table, passed_names).
    Pass rule: IR>0 and |NW t|>=t_thresh and not a full collapse late (IR_late > 0).
    """
    rows = {}
    for name, S in signals.items():
        m = evaluate_signal(S, ret, L=L)
        m["PASS"] = bool(m["IR"] > 0 and abs(m["t_NW"]) >= t_thresh and m["IR_late"] > 0)
        rows[name] = m
    tbl = pd.DataFrame(rows).T
    passed = [n for n in signals if rows[n]["PASS"]]
    return tbl, passed


if __name__ == "__main__":
    rng = np.random.default_rng(0)
    days = pd.bdate_range("2015-01-01", periods=1500)
    tks = [f"T{i}" for i in range(40)]
    truth = pd.DataFrame(rng.normal(size=(len(days), len(tks))), index=days, columns=tks)
    ret = truth.shift(-1)*0.003 + rng.normal(0, 0.015, truth.shape)  # weak real signal
    good = truth + rng.normal(0, 1.0, truth.shape)
    junk = pd.DataFrame(rng.normal(size=truth.shape), index=days, columns=tks)
    tbl, passed = gate({"good": good, "junk": junk}, ret)
    print(tbl.to_string()); print("passed:", passed)
