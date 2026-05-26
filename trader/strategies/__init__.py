"""Auto-import every strategy module so subclasses register on import.

Skips: `base.py`, `__init__.py`, and any underscore-prefixed module
(e.g. `_helpers.py`). Import failures are logged via `warnings.warn`
so one broken module doesn't disable the whole CLI.
"""
import importlib
import pkgutil
import warnings

from trader.strategies.base import BaseStrategy, STRATEGY_REGISTRY  # noqa: F401

for _info in pkgutil.iter_modules(__path__):
    if _info.name == "base" or _info.name.startswith("_"):
        continue
    try:
        importlib.import_module(f"{__name__}.{_info.name}")
    except Exception as exc:  # noqa: BLE001 — surface ANY import problem clearly
        warnings.warn(f"Failed to import strategy module {_info.name!r}: {exc}",
                       RuntimeWarning, stacklevel=2)
