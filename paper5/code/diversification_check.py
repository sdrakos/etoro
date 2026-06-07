#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Basket diversification gate (the ai-trading skill's 'diversity > count' test) on our cached
Yahoo baskets. Two products at rho~0.9 are ONE bet, not two. Reports avg |pairwise correlation| and
the EFFECTIVE NUMBER OF INDEPENDENT BETS  ENB = (sum lambda)^2 / sum(lambda^2)  over the correlation
eigenvalues (= N if all uncorrelated, -> 1 if all identical). This is the quantitative reason the
8-crypto DMN collapsed: a redundant basket gives the portfolio-Sharpe loss almost no signal."""
from __future__ import annotations
import sys, os
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import crypto_data, combined_data


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


def basket_stats(close_df):
    """close (T,N) DataFrame -> (corr (N,N), avg|rho|, ENB). Pairwise-complete daily returns."""
    rr = close_df.pct_change()
    corr = rr.corr().to_numpy()
    corr = np.nan_to_num(corr, nan=0.0)
    np.fill_diagonal(corr, 1.0)
    return corr, avg_abs_offdiag(corr), effective_bets(corr)


def _report(tag, close_df):
    corr, avg, enb = basket_stats(close_df)
    n = corr.shape[0]
    print(f"\n=== diversification [{tag}] — {n} assets, "
          f"{close_df.index[0].date()}..{close_df.index[-1].date()} ===")
    print(f"  avg |pairwise corr|        = {avg:.2f}")
    print(f"  effective independent bets = {enb:.1f} / {n}  ({enb / n * 100:.0f}% of nominal)")
    return tag, n, avg, enb


def main():
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    FIG = os.path.join(HERE, "..", "figures"); os.makedirs(FIG, exist_ok=True)
    crypto = crypto_data.fetch_crypto_daily()
    combined = combined_data.fetch_combined_daily()
    rows = [_report("crypto8", crypto), _report("combined18", combined)]

    fig, axes = plt.subplots(1, 2, figsize=(15, 6.5))
    for ax, (tag, df) in zip(axes, [("crypto8", crypto), ("combined18", combined)]):
        corr, avg, enb = basket_stats(df)
        n = corr.shape[0]
        im = ax.imshow(corr, vmin=-1, vmax=1, cmap="RdBu_r")
        ax.set_xticks(range(n)); ax.set_xticklabels(df.columns, rotation=45, ha="right", fontsize=7)
        ax.set_yticks(range(n)); ax.set_yticklabels(df.columns, fontsize=7)
        ax.set_title(f"{tag}: avg |rho| {avg:.2f} | ENB {enb:.1f}/{n} ({enb/n*100:.0f}%)")
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig_diversification.png"), dpi=130); plt.close()
    print(f"\n[fig] figures/fig_diversification.png")
    print("\nInterpretation: lower ENB -> fewer real bets -> weaker portfolio-Sharpe training signal.")


if __name__ == "__main__":
    main()
