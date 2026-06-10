"""Axis 1 — robustness / anti-overfit. Sweep the rule's knobs, score net-IR, and pick the
base config from the CENTER of the stable plateau (not the argmax — that is the overfit move)."""
from __future__ import annotations
import itertools

import numpy as np


def sweep(grid, score_fn):
    """grid: dict knob->list. score_fn(**combo)->net_ir. Returns list of {**combo, net_ir}."""
    keys = list(grid)
    rows = []
    for vals in itertools.product(*(grid[k] for k in keys)):
        combo = dict(zip(keys, vals))
        combo["net_ir"] = float(score_fn(**combo))
        rows.append(combo)
    return rows


def stable_center(rows, key, neighbor_span=1):
    """Pick the base config from the CENTER of a stable plateau along `key`, never the argmax.

    A single high spike is the overfit trap: the argmax is the LEAST trustworthy config. We instead
    locate a *plateau* — a contiguous run of `key` values whose scores are mutually consistent (each
    within `neighbor_span` window agreement) and high — and return the value at its centre.

    Method: for each distinct `key` value take a representative score (mean net_ir over the other
    knobs). Slide a window of half-width `neighbor_span`; a value is "plateau-grade" if its own score
    is close to that window's median (so an isolated spike, far above its neighbours, is excluded).
    Among all plateau-grade values keep the longest contiguous run and return the row at its centre."""
    vals = sorted({r[key] for r in rows})
    per_val = {v: float(np.mean([r["net_ir"] for r in rows if r[key] == v])) for v in vals}
    scores = [per_val[v] for v in vals]
    spread = float(np.std(scores)) or 1.0

    # plateau-grade = score agrees with its neighbourhood median (spikes deviate and are dropped)
    plateau = []
    for i, v in enumerate(vals):
        lo, hi = max(0, i - neighbor_span), min(len(vals), i + neighbor_span + 1)
        med = float(np.median([scores[j] for j in range(lo, hi)]))
        plateau.append(abs(scores[i] - med) <= 0.5 * spread)

    # longest contiguous run of plateau-grade values; tie-break on the higher mean level
    best_run, best_level, run = None, -np.inf, []
    def flush(run):
        nonlocal best_run, best_level
        if not run:
            return
        level = float(np.mean([scores[i] for i in run]))
        if (best_run is None) or (len(run) > len(best_run)) or (
                len(run) == len(best_run) and level > best_level):
            best_run, best_level = list(run), level
    for i, ok in enumerate(plateau):
        if ok:
            run.append(i)
        else:
            flush(run); run = []
    flush(run)
    if best_run is None:                       # no plateau at all → fall back to the top value
        best_run = [int(np.argmax(scores))]

    centre_val = vals[best_run[len(best_run) // 2]]
    cands = [r for r in rows if r[key] == centre_val]
    return max(cands, key=lambda r: r["net_ir"])


def robust_pick(rows, knobs, neighbor_span=1):
    """Pick the config in the INTERIOR of the best stable plateau across ALL `knobs` jointly
    (anti-overfit: rewards a config surrounded by other good configs, penalizes isolated spikes
    and grid-edge cells that have few good neighbours). For each row, score it by its joint
    neighbourhood (all rows within +/-neighbor_span grid-index on EVERY knob axis); return the
    max-scoring row. `knobs`: list of knob names that form the grid axes.

    The neighbourhood is summarised by its MEDIAN, not its mean: a single bright spike cannot
    pull a corner cell's score up (a mean lets one 5.0 outlier win a tiny 4-cell corner), so an
    isolated argmax/grid-edge spike is rejected and only a genuine plateau (a majority of good
    neighbours) scores high. Ties break toward the cell with the LARGER neighbourhood (true
    interior over edge), then the higher own net_ir."""
    axes = {k: sorted({r[k] for r in rows}) for k in knobs}
    pos = {k: {v: i for i, v in enumerate(axes[k])} for k in knobs}
    best, best_key = None, None
    for r in rows:
        neigh = [x["net_ir"] for x in rows
                 if all(abs(pos[k][x[k]] - pos[k][r[k]]) <= neighbor_span for k in knobs)]
        # median = spike-robust centre of the joint neighbourhood; bigger neighbourhood = interior
        key = (float(np.median(neigh)), len(neigh), r["net_ir"])
        if best_key is None or key > best_key:
            best, best_key = r, key
    return best
