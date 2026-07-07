from ddbot.state.store import PatternStore
from ddbot.watchlist import add_symbols, parse_symbols, remove_symbols


def _store(tmp_path, seed=("AAPL", "MSFT")):
    s = PatternStore(str(tmp_path / "s.sqlite3"))
    s.seed_watchlist(list(seed))
    return s


def test_add_symbols_validates_dedupes_and_flags(tmp_path):
    s = _store(tmp_path)
    # PLTR valid & new; AAPL already tracked; ZZZZ fails validation
    added, dupes, rejected = add_symbols(
        s, parse_symbols("pltr aapl zzzz"), validate=lambda t: t != "ZZZZ"
    )
    assert added == ["PLTR"]
    assert dupes == ["AAPL"]
    assert rejected == ["ZZZZ"]
    assert "PLTR" in s.list_tickers()


def test_remove_symbols(tmp_path):
    s = _store(tmp_path)
    assert remove_symbols(s, parse_symbols("aapl nope")) == ["AAPL"]
    assert s.list_tickers() == ["MSFT"]


def test_parse_symbols_here_too(tmp_path):
    assert parse_symbols("aapl, $tsla  nvda AAPL") == ["AAPL", "TSLA", "NVDA"]
    assert parse_symbols("!!! ...") == []
