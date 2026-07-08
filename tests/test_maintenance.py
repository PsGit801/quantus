from datetime import date

from ddbot.maintenance import dedupe_alerted
from ddbot.patterns.base import DoubleBottom, PatternState
from ddbot.state.store import PatternStore


def _alerted(store, b1_day, b2_day, neckline):
    """Insert an alerted CONFIRMED pattern (same ticker/tf/confirm_date, distinct pattern_id)."""
    p = DoubleBottom(
        ticker="T", timeframe="1d", b1_date=date(2024, 1, b1_day), b1_low=100.0,
        b2_date=date(2024, 1, b2_day), b2_low=100.0, peak_date=date(2024, 1, 5),
        neckline=neckline, state=PatternState.CONFIRMED,
        confirm_date=date(2024, 2, 1), confirm_close=neckline + 1,
    )
    store.upsert_detected(p)
    store.update_state(p)
    store.mark_alerted(p.pattern_id)
    return p


def test_dedupe_keeps_highest_prominence_per_group(tmp_path):
    s = PatternStore(str(tmp_path / "s.sqlite3"))
    # 3 alerts, same ticker/tf/confirm_date, different bottoms -> distinct ids, different necklines.
    _alerted(s, 1, 10, neckline=105.0)   # prominence 5%
    _alerted(s, 2, 11, neckline=112.0)   # prominence 12% -> should be kept
    _alerted(s, 3, 12, neckline=108.0)   # prominence 8%
    # a separate, unrelated single alert (different confirm_date) -> untouched
    lone = DoubleBottom(
        ticker="T", timeframe="1d", b1_date=date(2024, 3, 1), b1_low=100.0,
        b2_date=date(2024, 3, 10), b2_low=100.0, peak_date=date(2024, 3, 5),
        neckline=120.0, state=PatternState.CONFIRMED,
        confirm_date=date(2024, 3, 20), confirm_close=121.0,
    )
    s.upsert_detected(lone); s.update_state(lone); s.mark_alerted(lone.pattern_id)

    removed = dedupe_alerted(s.conn)
    assert removed == 2

    kept = s.alerted_patterns()
    assert len(kept) == 2  # one from the group + the lone one
    group_necklines = [p.neckline for p in kept if p.confirm_date == date(2024, 2, 1)]
    assert group_necklines == [112.0]  # strongest survived
    s.close()


def test_dedupe_noop_when_no_duplicates(tmp_path):
    s = PatternStore(str(tmp_path / "s.sqlite3"))
    _alerted(s, 1, 10, neckline=110.0)
    assert dedupe_alerted(s.conn) == 0
    s.close()
