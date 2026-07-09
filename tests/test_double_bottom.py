from datetime import date

from _synthetic import TEST_CFG, _CLOSE, _HIGH, _LOW, _OPEN, _VOL, flush_reclaim, make_ohlcv

from ddbot.patterns.base import DoubleBottom, PatternState
from ddbot.patterns.double_bottom import check_confirmation, dedupe_by_neckline, detect


# --- detection ------------------------------------------------------------------

def test_detects_flush_reclaim():
    pats = detect(flush_reclaim(), "T", "1d", TEST_CFG)
    assert len(pats) == 1
    p = pats[0]
    assert p.b1_date == date(2024, 1, 6)    # B1 idx5
    assert p.b2_date == date(2024, 1, 16)   # flush low idx15
    assert p.b2_low < p.b1_low              # undercut
    assert p.neckline == 114.0              # interim peak
    assert p.stop_reference == p.b2_low     # stop is the flush low


def test_no_pattern_without_undercut():
    # Raise the flush low above B1's low -> no bear-trap -> rejected.
    lows = list(_LOW)
    lows[15] = 101.0  # above B1 low (100)
    df = make_ohlcv(lows, _HIGH, _CLOSE, _OPEN, _VOL)
    assert detect(df, "T", "1d", TEST_CFG) == []


def test_no_pattern_when_not_steep():
    cfg = TEST_CFG.model_copy(update={"flush_atr_mult": 50.0})
    assert detect(flush_reclaim(), "T", "1d", cfg) == []


def test_no_pattern_without_volume_spike():
    vol = [1000] * 20  # no capitulation spike on the flush bar
    df = make_ohlcv(_LOW, _HIGH, _CLOSE, _OPEN, vol)
    assert detect(df, "T", "1d", TEST_CFG) == []


# --- confirmation ---------------------------------------------------------------

def test_confirms_on_reclaim():
    df = flush_reclaim()
    p = detect(df, "T", "1d", TEST_CFG)[0]
    res = check_confirmation(p, df, TEST_CFG)
    assert res.state is PatternState.CONFIRMED
    assert res.confirm_date == date(2024, 1, 18)  # reclaim idx17
    assert res.confirm_close == 103.0             # entry (below neckline 114)


def test_invalidated_on_deeper_flush_before_reclaim():
    closes = list(_CLOSE)
    closes[16] = 85.0  # closes below the flush low (88) -> failed
    df = make_ohlcv(_LOW, _HIGH, closes, _OPEN, _VOL)
    p = detect(df, "T", "1d", TEST_CFG)[0]
    assert check_confirmation(p, df, TEST_CFG).state is PatternState.INVALIDATED


def test_invalidated_when_reclaim_window_elapses():
    closes = list(_CLOSE)
    opens = list(_OPEN)
    for i in (16, 17, 18, 19):
        closes[i], opens[i] = 92.0, 95.0  # bearish, below B1 low; never reclaims
    df = make_ohlcv(_LOW, _HIGH, closes, opens, _VOL)
    p = detect(df, "T", "1d", TEST_CFG)[0]
    assert check_confirmation(p, df, TEST_CFG).state is PatternState.INVALIDATED


# --- dedup (unchanged logic) ----------------------------------------------------

def _p(b1, b2, peak, neckline, b1_low=100.0, b2_low=90.0):
    return DoubleBottom(
        ticker="T", timeframe="1d",
        b1_date=date(2024, 1, b1), b1_low=b1_low,
        b2_date=date(2024, 1, b2), b2_low=b2_low,
        peak_date=date(2024, 1, peak), neckline=neckline,
    )


def test_dedupe_keeps_strongest_per_neckline():
    shallow = _p(2, 8, peak=5, neckline=112.0, b1_low=108.0, b2_low=100.0)
    deep = _p(1, 8, peak=5, neckline=112.0, b1_low=100.0, b2_low=88.0)  # deeper -> winner
    out = dedupe_by_neckline([shallow, deep])
    assert len(out) == 1 and out[0].b2_low == 88.0


def test_dedupe_keeps_distinct_necklines():
    a = _p(1, 8, peak=5, neckline=112.0)
    b = _p(10, 18, peak=14, neckline=125.0)  # ~12% apart -> distinct
    assert len(dedupe_by_neckline([a, b])) == 2
