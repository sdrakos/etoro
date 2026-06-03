"""Typed request models for the core eToro trading actions (from the official spec)."""
from __future__ import annotations
from typing import Any, List, Optional
from pydantic import BaseModel


class UnifiedOrderRequest(BaseModel):
    """eToro v2 UnifiedOrderRequest. Only `action` and `transaction` are required;
    send the rest as needed. Serialize with model_dump(exclude_none=True)."""
    action: str
    transaction: str
    symbol: Optional[str] = None
    instrumentId: Optional[int] = None
    settlementType: Optional[str] = None
    orderType: Optional[str] = None
    triggerRate: Optional[float] = None
    leverage: Optional[int] = None
    amount: Optional[float] = None
    orderCurrency: Optional[str] = None
    units: Optional[float] = None
    contracts: Optional[float] = None
    stopLossRate: Optional[float] = None
    takeProfitRate: Optional[float] = None
    stopLossType: Optional[str] = None
    additionalMargin: Optional[float] = None
    positionIds: Optional[List[Any]] = None


class ClosePositionRequest(BaseModel):
    """eToro market-close-orders body (PascalCase per spec)."""
    InstrumentID: int
    UnitsToDeduct: Optional[float] = None
