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
