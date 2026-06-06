"""Diversified ETF basket for paper4's time-series-momentum setting.

The key is ASSET-CLASS diversity (low cross-correlation), not name count: a handful of
genuinely independent instruments (equities, bonds, gold, commodities, FX, real estate,
sectors) drives the result. See paper4 design spec section 12.
"""
START = "2007-01-01"
END = "2024-12-31"

# 18 liquid ETFs across asset classes
TICKERS = [
    "SPY", "QQQ", "IWM", "EFA", "EEM",          # equities (US large/tech/small, intl, EM)
    "TLT", "IEF", "LQD", "HYG",                  # bonds (long/mid Treasuries, IG, HY credit)
    "GLD", "SLV", "DBC", "USO",                  # gold, silver, broad commodities, oil
    "UUP",                                        # US dollar
    "VNQ",                                        # real estate
    "XLE", "XLF", "XLK",                          # sectors (energy, financials, tech)
]

# Minimal genuinely-uncorrelated diversifiers (used in the diversification ablation)
DIVERSIFIERS = ["TLT", "IEF", "GLD", "DBC", "UUP"]
