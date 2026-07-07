from datetime import date

from ddbot.backtest.engine import Trade
from ddbot.backtest.metrics import equity_curve
from ddbot.risk import position_size


def test_position_size_normal():
    # $10k, risk 1% = $100; risk/share = 110-100 = 10 -> 10 shares.
    s = position_size(entry=110.0, stop=100.0, equity=10000.0, risk_pct=0.01, max_position_pct=1.0)
    assert s.shares == 10
    assert s.dollar_risk == 100.0
    assert s.position_value == 1100.0
    assert s.capped is False


def test_position_size_capped_by_max_position():
    # Tiny stop -> risk model wants many shares, but 25% cap limits it.
    # risk/share = 0.10; risk 1% of 10k = 100 -> 1000 shares wanted.
    # max position 25% of 10k = 2500 / entry 50 = 50 shares -> capped.
    s = position_size(entry=50.0, stop=49.9, equity=10000.0, risk_pct=0.01, max_position_pct=0.25)
    assert s.shares == 50
    assert s.capped is True
    assert s.position_value == 2500.0


def test_position_size_zero_or_negative_risk():
    assert position_size(entry=100.0, stop=100.0, equity=10000.0, risk_pct=0.01).shares == 0
    assert position_size(entry=100.0, stop=110.0, equity=10000.0, risk_pct=0.01).shares == 0


def _t(r, entry_d, exit_d):
    return Trade(
        ticker="T", timeframe="1d", entry_date=entry_d, entry=100.0, stop=90.0, target=120.0,
        exit_date=exit_d, exit=100.0, r_multiple=r, return_pct=r, bars_held=1, outcome="win",
    )


def test_equity_curve_compounding_and_drawdown():
    # risk 10% per trade; R sequence +1, -1, +1 (by exit date).
    trades = [
        _t(1.0, date(2024, 1, 1), date(2024, 1, 10)),
        _t(-1.0, date(2024, 1, 11), date(2024, 1, 20)),
        _t(1.0, date(2024, 1, 21), date(2024, 1, 30)),
    ]
    e = equity_curve(trades, start_equity=1000.0, risk_pct=0.10)
    # 1000 * 1.1 = 1100 ; * 0.9 = 990 ; * 1.1 = 1089
    assert e.final_equity == 1089.0
    assert e.trades == 3
    # peak 1100 -> trough 990 => drawdown ~10%
    assert abs(e.max_drawdown_pct - 10.0) < 0.01


def test_equity_curve_empty():
    e = equity_curve([], start_equity=5000.0, risk_pct=0.01)
    assert e.final_equity == 5000.0 and e.trades == 0
