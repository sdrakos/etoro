"""Diversification check: the daily-return correlation matrix of the products that go into the model.

This is the quantitative test behind "diversity > count": redundant (highly-correlated) products add
turnover and cost without adding a real bet. Reports the correlation heatmap, the average absolute
pairwise correlation, and the EFFECTIVE NUMBER OF INDEPENDENT BETS (ENB) — from the eigenvalues of
the correlation matrix, ENB = (Σλ)² / Σλ² = N² / Σλ²  (= N if all uncorrelated, → 1 if all identical).

CLI:  python paper4/engine/correlation_check.py SPY TLT GLD USO UUP --tag div5
"""
from __future__ import annotations
import os
import numpy as np

from etoro_backtest import _fetch_etoro_closes, _ffill   # reuse the live eToro fetch


def return_corr(close):
    """(T,N) closes -> (corr (N,N), tickers-order returns). Daily simple returns, NaNs zeroed."""
    close = _ffill(close)
    rr = np.nan_to_num(close[1:] / close[:-1] - 1.0)
    return np.corrcoef(rr, rowvar=False), rr


def effective_bets(corr):
    """Effective number of independent bets from the correlation eigenvalues."""
    lam = np.linalg.eigvalsh(corr)
    lam = lam[lam > 0]
    return float(lam.sum() ** 2 / (lam ** 2).sum())


def avg_abs_offdiag(corr):
    n = corr.shape[0]
    if n < 2:
        return 0.0
    iu = np.triu_indices(n, k=1)
    return float(np.abs(corr[iu]).mean())


def run(tickers, tag="basket"):
    import json
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    close, dates, kept, id2tk = _fetch_etoro_closes(tickers)
    labels = [id2tk[i] for i in kept]
    corr, _rr = return_corr(close)
    enb, avg = effective_bets(corr), avg_abs_offdiag(corr)
    n = len(labels)
    print(f"\n=== correlation check [{tag}] — {n} products, {dates[0]}..{dates[-1]} ===")
    print(f"  avg |pairwise corr| = {avg:.2f}")
    print(f"  effective independent bets = {enb:.1f} / {n}  ({enb/n*100:.0f}% of nominal)")

    FIG = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "figures"))
    plt.rcParams.update({"font.family": "serif", "figure.dpi": 150, "savefig.bbox": "tight"})
    fig, ax = plt.subplots(figsize=(0.7 * n + 2, 0.7 * n + 1.5))
    im = ax.imshow(corr, vmin=-1, vmax=1, cmap="RdBu_r")
    ax.set_xticks(range(n)); ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_yticks(range(n)); ax.set_yticklabels(labels)
    for i in range(n):
        for j in range(n):
            ax.text(j, i, f"{corr[i, j]:.2f}", ha="center", va="center",
                    color="white" if abs(corr[i, j]) > 0.55 else "black", fontsize=8)
    ax.set_title(f"Daily-return correlation [{tag}] — avg |ρ| {avg:.2f}, "
                 f"effective bets {enb:.1f}/{n}")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, f"fig_correlation_{tag}.png")); plt.close(fig)
    with open(os.path.join(os.path.dirname(__file__), "..", f"results_correlation_{tag}.json"),
              "w", encoding="utf-8") as f:
        json.dump({"tickers": labels, "avg_abs_corr": avg, "effective_bets": enb,
                   "n": n, "corr": corr.tolist()}, f, indent=2)
    print(f"  saved figures/fig_correlation_{tag}.png + results_correlation_{tag}.json")
    return corr, labels, enb, avg


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Correlation/diversification check on real eToro prices.")
    ap.add_argument("tickers", nargs="*", help="product tickers")
    ap.add_argument("--tag", default="basket", help="label for the figure/results filename")
    a = ap.parse_args()
    run(a.tickers or ["SPY", "TLT", "GLD", "USO", "UUP"], tag=a.tag)
