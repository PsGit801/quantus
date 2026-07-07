from datetime import date

import pandas as pd

from ddbot.mtf import is_uptrend


def _weekly(closes, start="2024-01-01"):
    idx = pd.date_range(start, periods=len(closes), freq="7D")
    return pd.DataFrame({"open": closes, "high": closes, "low": closes,
                         "close": closes, "volume": [1] * len(closes)}, index=idx)


def test_uptrend_true_when_close_above_sma():
    df = _weekly([10, 11, 12, 13, 14, 15, 16, 17, 18, 19])  # rising
    assert is_uptrend(df, df.index[-1].date(), sma_window=5) is True


def test_downtrend_false_when_close_below_sma():
    df = _weekly([20, 19, 18, 17, 16, 15, 14, 13, 12, 11])  # falling
    assert is_uptrend(df, df.index[-1].date(), sma_window=5) is False


def test_insufficient_history_does_not_block():
    df = _weekly([10, 11, 12])  # fewer bars than sma_window
    assert is_uptrend(df, df.index[-1].date(), sma_window=30) is True


def test_no_lookahead_uses_bars_on_or_before_as_of():
    # Rising then a future spike; as_of before the spike -> judged on earlier (flat) bars.
    df = _weekly([10, 10, 10, 10, 10, 10, 100])
    as_of = df.index[4].date()  # before the spike
    # last close on/before as_of is 10, SMA(5) of [10,10,10,10,10] = 10 -> not > sma
    assert is_uptrend(df, as_of, sma_window=5) is False


def test_empty_df_does_not_block():
    assert is_uptrend(pd.DataFrame(), date(2024, 6, 1), sma_window=10) is True
