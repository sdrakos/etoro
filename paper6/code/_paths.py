# paper6/code/_paths.py
"""Put the proven helper dirs on sys.path so bare imports resolve. Import this FIRST.
paper4/code: costs, metrics, sizing.  paper5/code: band_eval, crypto_data, crypto_features."""
from __future__ import annotations
import os
import sys

_HERE = os.path.dirname(__file__)
for _rel in (("..", "..", "paper4", "code"), ("..", "..", "paper5", "code")):
    _p = os.path.join(_HERE, *_rel)
    if _p not in sys.path:
        sys.path.insert(0, _p)
