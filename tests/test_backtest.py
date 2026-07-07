from datetime import date

import pandas as pd
from _synthetic import TEST_CFG, W_LOWS, make_ohlcv

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


def _pattern(df, neckline=110.0, base=100.0, entry=110.0, confirm_i=2):
    return DoubleBottom(
        ticker="T", timeframe="1d",
        b1_date=date(2024, 1, 1), b1_low=base,
        b2_date=date(2024, 1, 10), b2_low=base,
        peak_date=date(2024, 1, 5), neckline=neckline,
        state=PatternState.CONFIRMED,
        confirm_date=df.index[confirm_i].date(), confirm_close=entry,
    )


# --- trade simulation -----------------------------------------------------------

def test_simulate_win_at_measured_move_target():
    # entry 110, stop 100, target = 110 + (110-100) = 120 -> R = 1.0
    df = _forward_df(
        highs=[111, 111, 111, 121, 121, 121],
        lows=[109, 109, 109, 111, 111, 111],
        closes=[110, 110, 110, 115, 115, 115],
    )
    tr = simulate_trade(df, _pattern(df), BacktestConfig(max_hold_bars=60))
    assert tr.outcome == "win"
    assert tr.r_multiple == 1.0
    assert tr.bars_held == 1
    assert tr.exit == 120.0


def test_simulate_loss_at_stop():
    df = _forward_df(
        highs=[111, 111, 111, 111, 111, 111],
        lows=[109, 109, 109, 99, 99, 99],   # bar 3 pierces the stop (100)
        closes=[110, 110, 110, 105, 105, 105],
    )
    tr = simulate_trade(df, _pattern(df), BacktestConfig(max_hold_bars=60))
    assert tr.outcome == "loss"
    assert tr.r_multiple == -1.0
    assert tr.exit == 100.0


def test_simulate_timeout_exit_at_close():
    # Never hits stop or target within max_hold; time-exit at close.
    df = _forward_df(
        highs=[111, 111, 111, 112, 112, 112],
        lows=[109, 109, 109, 105, 105, 105],
        closes=[110, 110, 110, 111, 112, 113],
    )
    tr = simulate_trade(df, _pattern(df), BacktestConfig(max_hold_bars=2))
    assert tr.outcome == "timeout"
    assert tr.bars_held == 2


def test_simulate_skips_degenerate_risk():
    df = _forward_df([111] * 4, [109] * 4, [110] * 4)
    # target <= entry when entry already at/above measured move
    p = _pattern(df, neckline=110.0, base=100.0, entry=125.0)  # target 120 < entry 125
    assert simulate_trade(df, p, BacktestConfig()) is None


# --- walk-forward signal discovery ---------------------------------------------

def test_find_signals_no_lookahead():
    # 23-bar series: 5 leading bars + the clean W; lookback window fits the whole W.
    lows = [116, 114, 112, 110, 108] + list(W_LOWS)
    df = make_ohlcv(lows)
    b = df.columns
    df.iloc[22, b.get_loc("open")] = 109.0   # breakout candle (W's idx17 -> combined idx22)
    df.iloc[22, b.get_loc("close")] = 113.0
    df.iloc[22, b.get_loc("high")] = 113.5
    cfg = TEST_CFG.model_copy(update={"lookback_bars": 20})

    sigs = find_signals(df, "T", "1d", cfg)
    assert len(sigs) == 1
    s = sigs[0]
    assert s.state is PatternState.CONFIRMED
    assert s.confirm_date == df.index[22].date()  # entry is the breakout bar, not earlier


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
    assert s.profit_factor == 1.5  # gross win 3 / gross loss 2


def test_max_drawdown_r():
    # cumulative R: 2, 1, 0, 1 -> peak 2, worst trough at 0 -> drawdown 2
    assert _max_drawdown_r([2.0, -1.0, -1.0, 1.0]) == 2.0


def test_summarize_empty():
    s = summarize([])
    assert s.trades == 0 and s.total_r == 0.0
