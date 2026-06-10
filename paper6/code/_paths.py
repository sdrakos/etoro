# paper6/code/_paths.py
"""Put the proven helper dirs on sys.path so bare imports resolve. Import this FIRST.
paper4/code: costs, metrics, sizing.  paper5/code: band_eval, crypto_data, crypto_features.

NOTE: we APPEND (not insert) so paper6/code's own modules always take precedence. paper4/code
contains a `data.py` that would otherwise shadow paper6's `data.py` if inserted at position 0;
appending keeps the local dir (sys.path[0] for the script/test run) winning, while the helper
names — which do NOT exist in paper6/code — are still found further down the path."""
from __future__ import annotations
import os
import sys

_HERE = os.path.dirname(__file__)
for _rel in (("..", "..", "paper4", "code"), ("..", "..", "paper5", "code")):
    _p = os.path.join(_HERE, *_rel)
    if _p not in sys.path:
        sys.path.append(_p)
