from datetime import date

import pytest

from ddbot.backtest.engine import Trade
from ddbot.backtest.metrics import summarize
from ddbot.backtest.walkforward import (
    anchored_oos,
    rolling_folds,
    walk_forward_report,
)


def _trade(entry_date: date, r: float = 1.0) -> Trade:
    outcome = "win" if r > 0 else "loss"
    return Trade(
        ticker="T", timeframe="1d", entry_date=entry_date, entry=100.0, stop=90.0,
        target=120.0, exit_date=entry_date, exit=100.0 + 10.0 * r, r_multiple=r,
        return_pct=r, bars_held=1, outcome=outcome,
    )


def test_rolling_folds_count_and_labels():
    trades = [_trade(date(2024, 1, 1)), _trade(date(2024, 7, 1)), _trade(date(2024, 12, 31))]
    folds = rolling_folds(trades, 3)
    assert len(folds) == 3
    for label, _ in folds:
        assert "…" in label  # "YYYY-MM-DD…YYYY-MM-DD"


def test_rolling_folds_partition_is_complete_and_disjoint():
    trades = [_trade(date(2024, 1, 1) + __import__("datetime").timedelta(days=10 * i)) for i in range(30)]
    folds = rolling_folds(trades, 4)
    counted = sum(len(t) for _, t in folds)
    assert counted == len(trades)  # every trade lands in exactly one fold
    # Folds are contiguous by entry date: each fold's max < next fold's min.
    non_empty = [ts for _, ts in folds if ts]
    for earlier, later in zip(non_empty, non_empty[1:]):
        assert max(t.entry_date for t in earlier) <= min(t.entry_date for t in later)


def test_rolling_folds_last_trade_included():
    trades = [_trade(date(2024, 1, 1)), _trade(date(2024, 12, 31))]
    folds = rolling_folds(trades, 2)
    # The final trade must appear somewhere (last window is inclusive).
    assert any(any(t.entry_date == date(2024, 12, 31) for t in ts) for _, ts in folds)


def test_rolling_folds_keeps_empty_folds():
    # Two trades clustered at the extremes, 4 folds -> middle folds are empty but kept.
    trades = [_trade(date(2024, 1, 1)), _trade(date(2024, 12, 31))]
    folds = rolling_folds(trades, 4)
    assert len(folds) == 4
    assert any(len(ts) == 0 for _, ts in folds)


def test_rolling_folds_empty_input():
    assert rolling_folds([], 3) == []


def test_rolling_folds_rejects_bad_n():
    with pytest.raises(ValueError):
        rolling_folds([_trade(date(2024, 1, 1))], 0)


def test_anchored_oos_newest_fraction():
    trades = [_trade(date(2024, 1, 1)), _trade(date(2024, 6, 1)),
              _trade(date(2024, 9, 1)), _trade(date(2024, 12, 1))]
    train, test = anchored_oos(trades, 0.25)
    assert len(train) == 3 and len(test) == 1
    assert test[0].entry_date == date(2024, 12, 1)  # newest held out


def test_anchored_oos_sorts_before_splitting():
    trades = [_trade(date(2024, 12, 1)), _trade(date(2024, 1, 1)), _trade(date(2024, 6, 1))]
    train, test = anchored_oos(trades, 0.34)  # ~1 held out
    assert train[0].entry_date == date(2024, 1, 1)
    assert test[-1].entry_date == date(2024, 12, 1)


def test_anchored_oos_rejects_bad_fraction():
    with pytest.raises(ValueError):
        anchored_oos([_trade(date(2024, 1, 1))], 0.0)
    with pytest.raises(ValueError):
        anchored_oos([_trade(date(2024, 1, 1))], 1.0)


def test_walk_forward_report_flags_and_verdict():
    # Fold 1: 2 losing trades (below min_trades). Fold 2: 12 winning trades.
    import datetime as dt
    losers = [_trade(date(2024, 1, 1) + dt.timedelta(days=i), r=-1.0) for i in range(2)]
    winners = [_trade(date(2024, 6, 1) + dt.timedelta(days=i), r=1.0) for i in range(12)]
    trades = losers + winners
    folds = rolling_folds(trades, 2)
    overall = summarize(trades)
    report = walk_forward_report(folds, overall, min_trades=10, anchored=anchored_oos(trades, 0.3))
    assert "Walk-forward" in report
    assert "LOW" in report          # the 2-trade fold is flagged low-sample
    assert "Stability:" in report
    assert "Held-out newest slice:" in report
    assert "ALL" in report
