import pytest
from pydantic import ValidationError


def test_unified_order_requires_action_and_transaction():
    from etoro_api.models import UnifiedOrderRequest
    with pytest.raises(ValidationError):
        UnifiedOrderRequest(transaction="buy")  # missing action
    with pytest.raises(ValidationError):
        UnifiedOrderRequest(action="open")  # missing transaction


def test_unified_order_exclude_none_drops_optionals():
    from etoro_api.models import UnifiedOrderRequest
    m = UnifiedOrderRequest(action="open", transaction="buy",
                            instrumentId=100000, amount=100, leverage=1)
    body = m.model_dump(exclude_none=True)
    assert body == {"action": "open", "transaction": "buy",
                    "instrumentId": 100000, "amount": 100, "leverage": 1}
    assert "symbol" not in body and "units" not in body


def test_close_position_model():
    from etoro_api.models import ClosePositionRequest
    full = ClosePositionRequest(InstrumentID=100000)
    assert full.model_dump(exclude_none=True) == {"InstrumentID": 100000}
    partial = ClosePositionRequest(InstrumentID=100000, UnitsToDeduct=2.5)
    assert partial.model_dump(exclude_none=True) == {"InstrumentID": 100000, "UnitsToDeduct": 2.5}
