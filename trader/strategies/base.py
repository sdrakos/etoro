"""Strategy ABC + auto-registry.

Defining a class that inherits from BaseStrategy and sets `name` adds it to
STRATEGY_REGISTRY without manual edits. The CLI discovers strategies this way.
"""
from __future__ import annotations
from typing import ClassVar
import backtrader as bt

STRATEGY_REGISTRY: dict[str, type] = {}


class _AutoRegisterMeta(type(bt.Strategy)):
    def __init__(cls, name_attr, bases, namespace, **kwargs):
        super().__init__(name_attr, bases, namespace, **kwargs)
        cls_name = namespace.get("name")
        if cls_name and name_attr != "BaseStrategy":
            STRATEGY_REGISTRY[cls_name] = cls


class BaseStrategy(bt.Strategy, metaclass=_AutoRegisterMeta):
    """Subclass this, set `name` + `description` + `params_dataclass`."""
    name: ClassVar[str] = ""
    description: ClassVar[str] = ""
    params_dataclass: ClassVar[type] = type(None)

    def __init__(self):
        self._trade_log: list[dict] = []

    def log_trade(self, side: str, ticker: str, size: float, price: float, reason: str):
        self._trade_log.append({
            "datetime": self.datas[0].datetime.datetime(0).isoformat(),
            "side": side, "ticker": ticker, "size": size,
            "price": price, "reason": reason,
        })

    @classmethod
    def required_tickers(cls, params) -> list[str] | None:
        """Override if strategy hardcodes a universe; else return None."""
        return None
