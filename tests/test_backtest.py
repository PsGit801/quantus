from datetime import date

import pandas as pd
from _synthetic import TEST_CFG, flush_reclaim

from ddbot.backtest.engine import (
    BacktestConfig,
    Trade,
    find_signals,
    simulate_trade,
)
from ddbot.backtest.metrics import _max_drawdown_r, summarize
from ddbot.patterns.base import DoubleBottom, PatternState


def _forward_df(highs, lows, closes):
    idx = pd.date_range("2024-02-01", periods=len(highs), freq="D")
    return pd.DataFrame(
        {"open": closes, "high": highs, "low": lows, "close": closes, "volume": [1000] * len(highs)},
        index=idx,
    )


def _pattern(df, neckline=110.0, base=100.0, entry=105.0, confirm_i=2):
    # Reclaim entry sits below the neckline; target = neckline (default BacktestConfig).
    return DoubleBottom(
        ticker="T", timeframe="1d",
        b1_date=date(2024, 1, 1), b1_low=base,
        b2_date=date(2024, 1, 10), b2_low=base,
        peak_date=date(2024, 1, 5), neckline=neckline,
        state=PatternState.CONFIRMED,
        confirm_date=df.index[confirm_i].date(), confirm_close=entry,
    )


# --- trade simulation (target = neckline) ---------------------------------------

def test_simulate_win_at_neckline_target():
    # entry 105, stop 100, target = neckline 110 -> R = (110-105)/5 = 1.0
    df = _forward_df(
        highs=[106, 106, 106, 111, 111, 111],
        lows=[104, 104, 104, 106, 106, 106],
        closes=[105, 105, 105, 108, 108, 108],
    )
    tr = simulate_trade(df, _pattern(df), BacktestConfig(max_hold_bars=60))
    assert tr.outcome == "win"
    assert tr.r_multiple == 1.0
    assert tr.bars_held == 1
    assert tr.exit == 110.0


def test_simulate_loss_at_stop():
    df = _forward_df(
        highs=[106, 106, 106, 106, 106, 106],
        lows=[104, 104, 104, 99, 99, 99],   # bar 3 pierces the stop (100)
        closes=[105, 105, 105, 101, 101, 101],
    )
    tr = simulate_trade(df, _pattern(df), BacktestConfig(max_hold_bars=60))
    assert tr.outcome == "loss"
    assert tr.r_multiple == -1.0
    assert tr.exit == 100.0


def test_simulate_timeout_exit_at_close():
    df = _forward_df(
        highs=[106, 106, 106, 108, 108, 108],
        lows=[104, 104, 104, 103, 103, 103],
        closes=[105, 105, 105, 106, 107, 108],
    )
    tr = simulate_trade(df, _pattern(df), BacktestConfig(max_hold_bars=2))
    assert tr.outcome == "timeout"
    assert tr.bars_held == 2


def test_simulate_skips_degenerate_risk():
    df = _forward_df([111] * 4, [104] * 4, [105] * 4)
    p = _pattern(df, neckline=110.0, base=100.0, entry=112.0)  # entry above neckline target
    assert simulate_trade(df, p, BacktestConfig()) is None


# --- walk-forward signal discovery (no look-ahead) ------------------------------

def test_find_signals_confirms_on_reclaim():
    sigs = find_signals(flush_reclaim(), "T", "1d", TEST_CFG)
    assert len(sigs) == 1
    s = sigs[0]
    assert s.state is PatternState.CONFIRMED
    assert s.confirm_date == date(2024, 1, 18)  # the reclaim bar


# --- metrics --------------------------------------------------------------------

def _t(r, outcome="win", bars=1):
    return Trade(
        ticker="T", timeframe="1d", entry_date=date(2024, 1, 1), entry=100.0, stop=90.0,
        target=120.0, exit_date=date(2024, 1, 2), exit=100.0,
        r_multiple=r, return_pct=r, bars_held=bars, outcome=outcome,
    )


def test_summarize_math():
    s = summarize([_t(2.0), _t(-1.0, "loss"), _t(-1.0, "loss"), _t(1.0)])
    assert s.trades == 4
    assert s.wins == 2 and s.losses == 2
    assert s.win_rate == 50.0
    assert s.avg_r == 0.25
    assert s.total_r == 1.0
    assert s.profit_factor == 1.5


def test_max_drawdown_r():
    assert _max_drawdown_r([2.0, -1.0, -1.0, 1.0]) == 2.0


def test_summarize_empty():
    s = summarize([])
    assert s.trades == 0 and s.total_r == 0.0
