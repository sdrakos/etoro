from rebalancer import Order, plan


def test_open_new_positions_above_threshold():
    targets = {"SPY": 0.5, "TLT": -0.5}
    imap = {"SPY": 101, "TLT": 102}
    orders = plan([], targets, imap, capital=10000, min_trade=50)
    assert len(orders) == 2
    spy = [o for o in orders if o.ticker == "SPY"][0]
    assert spy.action == "open" and spy.is_buy and abs(spy.amount_eur - 5000) < 1e-6
    tlt = [o for o in orders if o.ticker == "TLT"][0]
    assert tlt.action == "open" and (not tlt.is_buy) and abs(tlt.amount_eur - 5000) < 1e-6


def test_skip_below_min_trade():
    orders = plan([], {"SPY": 0.001}, {"SPY": 101}, capital=10000, min_trade=50)
    assert orders == []


def test_close_position_not_in_target():
    current = [{"instrument_id": 101, "is_buy": True, "amount_eur": 3000}]
    orders = plan(current, {"TLT": 1.0}, {"TLT": 102, "SPY": 101}, capital=10000, min_trade=50)
    closed = [o for o in orders if o.action == "close"]
    assert len(closed) == 1 and closed[0].instrument_id == 101


def test_flip_direction_closes_then_opens():
    current = [{"instrument_id": 101, "is_buy": True, "amount_eur": 5000}]
    orders = plan(current, {"SPY": -0.5}, {"SPY": 101}, capital=10000, min_trade=50)
    assert orders[0].action == "close" and orders[0].is_buy
    assert orders[1].action == "open" and (not orders[1].is_buy)


def test_no_action_when_change_below_threshold():
    current = [{"instrument_id": 101, "is_buy": True, "amount_eur": 5000}]
    orders = plan(current, {"SPY": 0.5}, {"SPY": 101}, capital=10000, min_trade=50)
    assert orders == []
