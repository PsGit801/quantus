from datetime import date, timedelta

from ddbot.digest import format_digest, health_line
from ddbot.journal import Outcome
from ddbot.state.store import PatternStore


def _o(ticker, status, r, unreal=False):
    return Outcome(ticker, "1d", date(2026, 7, 1), 100.0, 90.0, 120.0, status, r, 100.0 + r, 5, unreal)


def test_format_digest_with_resolved_and_open():
    outs = [_o("W", "win", 2.0), _o("L", "loss", -1.0), _o("O", "open", 0.5, unreal=True)]
    msg = format_digest(outs, "🩺 Health: scan ok", since=date(2026, 7, 8))
    assert "3 alerts" in msg and "2 resolved" in msg and "1 open" in msg
    assert "Resolved: win 50%" in msg and "PF 2.00" in msg      # 2.0 win vs 1.0 loss
    assert "Open: 1 positions, +0.5R" in msg
    assert "🩺 Health: scan ok" in msg


def test_format_digest_empty():
    msg = format_digest([], "🩺 Health: scan ok", since=date(2026, 7, 8))
    assert "No alerts fired" in msg
    assert "Backtest ref" in msg


def test_health_line_fresh(tmp_path):
    s = PatternStore(str(tmp_path / "s.sqlite3"))
    s.seed_watchlist(["AAA", "BBB"])
    today = date(2026, 7, 15)
    s.kv_set("last_scan_at", today.isoformat())
    s.kv_set("last_listen_at", today.isoformat() + "T09:00:00")
    line = health_line(s, today)
    assert "⚠️" not in line
    assert "scan ok" in line and "listener ok" in line and "watchlist 2" in line
    s.close()


def test_health_line_stale_scan_warns(tmp_path):
    s = PatternStore(str(tmp_path / "s.sqlite3"))
    today = date(2026, 7, 15)
    s.kv_set("last_scan_at", (today - timedelta(days=5)).isoformat())
    line = health_line(s, today)
    assert "⚠️" in line and "5d stale" in line
    s.close()


def test_health_line_never_run_warns(tmp_path):
    s = PatternStore(str(tmp_path / "s.sqlite3"))
    line = health_line(s, date(2026, 7, 15))
    assert "⚠️" in line and "never run" in line
    s.close()
