from datetime import date

import pandas as pd

from ddbot.backtest.engine import BacktestConfig
from ddbot.journal import evaluate
from ddbot.patterns.base import DoubleBottom, PatternState
from ddbot.state.store import PatternStore


def _fwd(highs, lows, closes, start="2024-02-01"):
    idx = pd.date_range(start, periods=len(highs), freq="D")
    return pd.DataFrame({"open": closes, "high": highs, "low": lows,
                         "close": closes, "volume": [1000] * len(highs)}, index=idx)


def _sig(df, confirm_i=2, neckline=110.0, base=100.0, entry=110.0):
    return DoubleBottom(
        ticker="T", timeframe="1d", b1_date=date(2024, 1, 1), b1_low=base,
        b2_date=date(2024, 1, 10), b2_low=base, peak_date=date(2024, 1, 5),
        neckline=neckline, state=PatternState.CONFIRMED,
        confirm_date=df.index[confirm_i].date(), confirm_close=entry,
    )


def test_evaluate_win():
    # entry 110, stop 100, target 120 -> bar 3 hits target
    df = _fwd([111, 111, 111, 121, 121], [109, 109, 109, 112, 112], [110, 110, 110, 118, 118])
    o = evaluate(df, _sig(df), BacktestConfig(max_hold_bars=60))
    assert o.status == "win" and o.r_multiple == 1.0 and not o.unrealized


def test_evaluate_loss():
    df = _fwd([111, 111, 111, 111, 111], [109, 109, 109, 99, 99], [110, 110, 110, 103, 103])
    o = evaluate(df, _sig(df), BacktestConfig(max_hold_bars=60))
    assert o.status == "loss" and o.r_multiple == -1.0


def test_evaluate_open_when_unresolved_recent():
    # never hits stop/target, within max_hold, at end of data -> open (unrealized)
    df = _fwd([111, 111, 111, 112, 113], [109, 109, 109, 108, 109], [110, 110, 110, 111, 112])
    o = evaluate(df, _sig(df), BacktestConfig(max_hold_bars=60))
    assert o.status == "open" and o.unrealized is True


def test_evaluate_unknown_when_confirm_date_missing():
    df = _fwd([111, 111, 111], [109, 109, 109], [110, 110, 110])
    p = _sig(df)
    p = p.with_state(PatternState.CONFIRMED, confirm_date=date(1999, 1, 1))  # not in df
    o = evaluate(df, p, BacktestConfig())
    assert o.status == "unknown"


def test_alerted_patterns_returns_only_alerted(tmp_path):
    s = PatternStore(str(tmp_path / "s.sqlite3"))
    p = _sig(_fwd([1, 1, 1], [1, 1, 1], [1, 1, 1]))
    s.upsert_detected(p)
    assert s.alerted_patterns() == []       # not alerted yet
    s.update_state(p.with_state(PatternState.CONFIRMED, confirm_date=p.confirm_date, confirm_close=p.confirm_close))
    s.mark_alerted(p.pattern_id)
    got = s.alerted_patterns()
    assert len(got) == 1 and got[0].ticker == "T"
    s.close()
