from datetime import date

from _synthetic import TEST_CFG, W_LOWS, confirmed_w, make_ohlcv

from ddbot.patterns.base import DoubleBottom, PatternState
from ddbot.patterns.double_bottom import check_confirmation, dedupe_by_neckline, detect


def _p(b1, b2, peak, neckline, b1_low=100.0, b2_low=100.0):
    return DoubleBottom(
        ticker="T", timeframe="1d",
        b1_date=date(2024, 1, b1), b1_low=b1_low,
        b2_date=date(2024, 1, b2), b2_low=b2_low,
        peak_date=date(2024, 1, peak), neckline=neckline,
    )


def test_dedupe_keeps_strongest_per_neckline():
    # Same neckline price, different depth -> collapse to the deeper (more prominent) W.
    shallow = _p(2, 8, peak=5, neckline=112.0, b1_low=108.0, b2_low=108.0)  # ~3.7%
    deep = _p(1, 8, peak=5, neckline=112.0, b1_low=100.0, b2_low=100.0)     # 12% -> winner
    out = dedupe_by_neckline([shallow, deep])
    assert len(out) == 1 and out[0].b1_low == 100.0


def test_dedupe_clusters_near_necklines():
    # Necklines within the tolerance band (112.0 vs 113.0 ~0.9%) -> one alert.
    a = _p(1, 8, peak=5, neckline=112.0)
    b = _p(2, 9, peak=6, neckline=113.0)
    assert len(dedupe_by_neckline([a, b])) == 1


def test_dedupe_keeps_distinct_necklines():
    a = _p(1, 8, peak=5, neckline=112.0)
    b = _p(10, 18, peak=14, neckline=125.0)  # ~12% apart -> distinct setup
    out = dedupe_by_neckline([a, b])
    assert len(out) == 2


def test_detects_clean_w():
    df = make_ohlcv(W_LOWS)
    patterns = detect(df, "TEST", "1d", TEST_CFG)
    assert len(patterns) == 1
    p = patterns[0]
    assert p.b1_date == date(2024, 1, 6)   # idx 5
    assert p.b2_date == date(2024, 1, 16)  # idx 15
    assert p.neckline == 111.0
    assert p.stop_reference == 100.0
    assert p.state is PatternState.DETECTED


def test_bottoms_too_dissimilar_no_pattern():
    lows = list(W_LOWS)
    lows[15] = 90.0  # second bottom 10% below the first -> outside tolerance
    patterns = detect(make_ohlcv(lows), "TEST", "1d", TEST_CFG)
    assert patterns == []


def test_insufficient_prominence_no_pattern():
    # Flatten the intervening peak so the "W" has no depth.
    lows = [102, 101.5, 101, 100.5, 100, 99.5, 100, 100.5, 100.2, 100.4,
            100.3, 100.1, 100, 99.8, 99.9, 99.6, 101, 102]
    patterns = detect(make_ohlcv(lows), "TEST", "1d", TEST_CFG)
    assert patterns == []


def test_confirmation_on_bullish_breakout():
    df = confirmed_w()
    p = detect(df, "TEST", "1d", TEST_CFG)[0]
    confirmed = check_confirmation(p, df, TEST_CFG)
    assert confirmed.state is PatternState.CONFIRMED
    assert confirmed.confirm_date == date(2024, 1, 18)  # idx 17
    assert confirmed.confirm_close == 113.0


def test_no_confirmation_when_breakout_candle_is_red():
    df = confirmed_w()
    # Make the breakout candle bearish: close above neckline but below the open.
    df.iloc[17, df.columns.get_loc("open")] = 114.0  # close (113) < open -> red
    p = detect(df, "TEST", "1d", TEST_CFG)[0]
    result = check_confirmation(p, df, TEST_CFG)
    assert result.state is PatternState.DETECTED


def test_weak_volume_breakout_not_confirmed():
    df = confirmed_w()
    vol = df.columns.get_loc("volume")
    df.iloc[:, vol] = 1000.0            # baseline volume
    df.iloc[17, vol] = 100.0            # breakout candle on weak volume
    cfg = TEST_CFG.model_copy(update={"require_volume_confirmation": True, "volume_factor": 1.0})
    p = detect(df, "TEST", "1d", cfg)[0]
    assert check_confirmation(p, df, cfg).state is PatternState.DETECTED


def test_weak_volume_confirmed_when_gate_disabled():
    df = confirmed_w()
    vol = df.columns.get_loc("volume")
    df.iloc[:, vol] = 1000.0
    df.iloc[17, vol] = 100.0
    cfg = TEST_CFG.model_copy(update={"require_volume_confirmation": False})
    p = detect(df, "TEST", "1d", cfg)[0]
    assert check_confirmation(p, df, cfg).state is PatternState.CONFIRMED


def test_invalidation_on_close_below_bottoms():
    df = confirmed_w()
    # A close below the stop reference (100) after B2 invalidates the pattern.
    df.iloc[16, df.columns.get_loc("close")] = 99.0
    p = detect(df, "TEST", "1d", TEST_CFG)[0]
    result = check_confirmation(p, df, TEST_CFG)
    assert result.state is PatternState.INVALIDATED
