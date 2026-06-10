"""Axis 3 — diversification. ENB = (sum eigenvalues)^2 / sum(eigenvalues^2) of the return
correlation matrix (the 'effective number of independent bets'). Greedy selection maximizes it."""
from __future__ import annotations
import numpy as np


def effective_bets(returns):
    """returns: (T,N). ENB via the eigenvalues of the correlation matrix."""
    R = np.asarray(returns, float)
    R = R[np.isfinite(R).all(axis=1)]
    C = np.corrcoef(R, rowvar=False)
    lam = np.linalg.eigvalsh(C)
    lam = lam[lam > 0]
    return float((lam.sum() ** 2) / (np.square(lam).sum() + 1e-12))


def greedy_enb(returns, names, k):
    """Greedily add the asset that most increases ENB, until k chosen."""
    R = np.asarray(returns, float)
    remaining = list(range(len(names)))
    chosen = []
    while len(chosen) < k and remaining:
        best_j, best_enb = None, -np.inf
        for j in remaining:
            trial = chosen + [j]
            enb = effective_bets(R[:, trial]) if len(trial) > 1 else 1.0
            if enb > best_enb:
                best_j, best_enb = j, enb
        chosen.append(best_j)
        remaining.remove(best_j)
    return [names[j] for j in chosen]
