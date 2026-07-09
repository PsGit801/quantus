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


def _sig(df, confirm_i=2, neckline=115.0, base=100.0, entry=105.0):
    # Reclaim entry below the neckline; stop = base; target = neckline.
    return DoubleBottom(
        ticker="T", timeframe="1d", b1_date=date(2024, 1, 1), b1_low=base,
        b2_date=date(2024, 1, 10), b2_low=base, peak_date=date(2024, 1, 5),
        neckline=neckline, state=PatternState.CONFIRMED,
        confirm_date=df.index[confirm_i].date(), confirm_close=entry,
    )


def test_evaluate_win():
    # entry 105, stop 100, target = neckline 115 -> R = (115-105)/5 = 2.0
    df = _fwd([106, 106, 106, 116, 116], [104, 104, 104, 108, 108], [105, 105, 105, 110, 110])
    o = evaluate(df, _sig(df), BacktestConfig(max_hold_bars=60))
    assert o.status == "win" and o.r_multiple == 2.0 and not o.unrealized


def test_evaluate_loss():
    df = _fwd([106, 106, 106, 106, 106], [104, 104, 104, 99, 99], [105, 105, 105, 101, 101])
    o = evaluate(df, _sig(df), BacktestConfig(max_hold_bars=60))
    assert o.status == "loss" and o.r_multiple == -1.0


def test_evaluate_open_when_unresolved_recent():
    df = _fwd([106, 106, 106, 108, 110], [104, 104, 104, 103, 104], [105, 105, 105, 107, 109])
    o = evaluate(df, _sig(df), BacktestConfig(max_hold_bars=60))
    assert o.status == "open" and o.unrealized is True


def test_evaluate_split_rescales_stored_levels():
    # Stored on OLD scale (entry 110, stop 100, neckline 115). A 2:1 split halves the
    # re-fetched series (confirm close 55 -> ratio 0.5): entry 55, stop 50, target 57.5.
    df = _fwd([56, 56, 56, 58, 58], [54, 54, 54, 55, 55], [55, 55, 55, 56, 56])
    p = _sig(df, neckline=115.0, base=100.0, entry=110.0)
    o = evaluate(df, p, BacktestConfig(max_hold_bars=60))
    assert o.status == "win"
    assert abs(o.entry - 55.0) < 0.01
    assert abs(o.r_multiple - 0.5) < 0.01  # (57.5-55)/(55-50)


def test_evaluate_unknown_when_confirm_date_missing():
    df = _fwd([111, 111, 111], [109, 109, 109], [110, 110, 110])
    p = _sig(df).with_state(PatternState.CONFIRMED, confirm_date=date(1999, 1, 1))
    assert evaluate(df, p, BacktestConfig()).status == "unknown"


def test_alerted_patterns_returns_only_alerted(tmp_path):
    s = PatternStore(str(tmp_path / "s.sqlite3"))
    p = _sig(_fwd([1, 1, 1], [1, 1, 1], [1, 1, 1]))
    s.upsert_detected(p)
    assert s.alerted_patterns() == []
    s.update_state(p.with_state(PatternState.CONFIRMED, confirm_date=p.confirm_date, confirm_close=p.confirm_close))
    s.mark_alerted(p.pattern_id)
    got = s.alerted_patterns()
    assert len(got) == 1 and got[0].ticker == "T"
    s.close()
