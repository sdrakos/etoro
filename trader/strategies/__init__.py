"""Auto-import every strategy module so subclasses register on import."""
import importlib
import pkgutil

from trader.strategies.base import BaseStrategy, STRATEGY_REGISTRY  # noqa: F401

# Walk this package and import each module so its BaseStrategy subclass registers.
for _info in pkgutil.iter_modules(__path__):
    if _info.name not in ("base", "__init__"):
        importlib.import_module(f"{__name__}.{_info.name}")
