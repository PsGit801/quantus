from ddbot.state.store import PatternStore


def _store(tmp_path):
    return PatternStore(str(tmp_path / "s.sqlite3"))


def test_seed_only_when_empty(tmp_path):
    s = _store(tmp_path)
    s.seed_watchlist(["AAPL", "MSFT"])
    assert s.list_tickers() == ["AAPL", "MSFT"]
    # Seeding again with different defaults is a no-op (table already populated).
    s.seed_watchlist(["TSLA"])
    assert s.list_tickers() == ["AAPL", "MSFT"]


def test_add_is_idempotent(tmp_path):
    s = _store(tmp_path)
    assert s.add_ticker("NVDA") is True
    assert s.add_ticker("NVDA") is False
    assert s.list_tickers() == ["NVDA"]


def test_remove(tmp_path):
    s = _store(tmp_path)
    s.seed_watchlist(["AAPL", "MSFT"])
    assert s.remove_ticker("AAPL") is True
    assert s.remove_ticker("AAPL") is False
    assert s.list_tickers() == ["MSFT"]


def test_kv_roundtrip_and_delete(tmp_path):
    s = _store(tmp_path)
    assert s.kv_get("tg_offset") is None
    s.kv_set("tg_offset", "42")
    assert s.kv_get("tg_offset") == "42"
    s.kv_set("tg_offset", "43")  # upsert
    assert s.kv_get("tg_offset") == "43"
    s.kv_set("tg_offset", None)  # delete
    assert s.kv_get("tg_offset") is None
