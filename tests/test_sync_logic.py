from ddbot.state.store import PatternStore
from ddbot.sync import (
    build_watchlist_keyboard,
    handle_update,
    is_authorized,
    parse_symbols,
)

OWNER = 806402113
ALLOWED = {OWNER}


class FakeTG:
    def __init__(self):
        self.messages = []
        self.callbacks = []

    def send_message(self, chat_id, text, reply_markup=None):
        self.messages.append((chat_id, text, reply_markup))

    def answer_callback(self, callback_id, text=None):
        self.callbacks.append((callback_id, text))


def _store(tmp_path, seed=("AAPL", "MSFT")):
    s = PatternStore(str(tmp_path / "s.sqlite3"))
    s.seed_watchlist(list(seed))
    return s


# --- pure helpers ---------------------------------------------------------------

def test_parse_symbols_normalizes_and_dedupes():
    assert parse_symbols("aapl, $tsla  nvda AAPL") == ["AAPL", "TSLA", "NVDA"]


def test_parse_symbols_rejects_junk():
    assert parse_symbols("!!! @#$ ...") == []
    assert parse_symbols("") == []


def test_is_authorized():
    assert is_authorized(OWNER, ALLOWED) is True
    assert is_authorized("806402113", ALLOWED) is True  # string coerces
    assert is_authorized(999, ALLOWED) is False
    assert is_authorized(None, ALLOWED) is False


def test_keyboard_is_fixed_two_buttons():
    # Fixed size regardless of watchlist length.
    kb = build_watchlist_keyboard()
    rows = kb["inline_keyboard"]
    assert len(rows) == 1 and len(rows[0]) == 2
    assert [b["callback_data"] for b in rows[0]] == ["add", "remove"]


# --- dispatch -------------------------------------------------------------------

def test_start_shows_welcome(tmp_path):
    s = _store(tmp_path)
    tg = FakeTG()
    update = {"update_id": 1, "message": {"chat": {"id": OWNER}, "text": "/start"}}
    handle_update(update, s, tg, ALLOWED, validate=lambda t: True)
    assert tg.messages and "Welcome to" in tg.messages[0][1]
    assert "Quantus" in tg.messages[0][1]


def test_foreign_chat_is_ignored(tmp_path):
    s = _store(tmp_path)
    tg = FakeTG()
    update = {"update_id": 1, "message": {"chat": {"id": 424242}, "text": "/remove AAPL"}}
    handle_update(update, s, tg, ALLOWED, validate=lambda t: True)
    assert s.list_tickers() == ["AAPL", "MSFT"]  # unchanged
    assert tg.messages == [] and tg.callbacks == []


def test_add_command_validates_and_adds(tmp_path):
    s = _store(tmp_path)
    tg = FakeTG()
    seen = {}
    def validate(t):
        seen[t] = True
        return t != "ZZZZ"  # ZZZZ is "not found"
    update = {"update_id": 5, "message": {"chat": {"id": OWNER}, "text": "/add pltr zzzz"}}
    handle_update(update, s, tg, ALLOWED, validate=validate)
    assert "PLTR" in s.list_tickers()
    assert "ZZZZ" not in s.list_tickers()
    # a summary message + the refreshed list were sent
    assert any("Added" in m[1] for m in tg.messages)


def test_add_button_then_typed_symbol(tmp_path):
    s = _store(tmp_path)
    tg = FakeTG()
    # 1) user taps "➕ Add"
    cb = {"update_id": 10, "callback_query": {"id": "cb1", "data": "add",
          "message": {"chat": {"id": OWNER}}}}
    handle_update(cb, s, tg, ALLOWED, validate=lambda t: True)
    assert s.kv_get(f"awaiting:{OWNER}") == "add"
    # 2) next poll: user types the symbol
    msg = {"update_id": 11, "message": {"chat": {"id": OWNER}, "text": "coin"}}
    handle_update(msg, s, tg, ALLOWED, validate=lambda t: True)
    assert "COIN" in s.list_tickers()
    assert s.kv_get(f"awaiting:{OWNER}") is None  # flag cleared


def test_remove_button_then_typed_symbol(tmp_path):
    s = _store(tmp_path)
    tg = FakeTG()
    # 1) user taps "➖ Remove"
    cb = {"update_id": 30, "callback_query": {"id": "cb3", "data": "remove",
          "message": {"chat": {"id": OWNER}}}}
    handle_update(cb, s, tg, ALLOWED, validate=lambda t: True)
    assert s.kv_get(f"awaiting:{OWNER}") == "remove"
    # 2) next poll: user types the symbol to remove
    msg = {"update_id": 31, "message": {"chat": {"id": OWNER}, "text": "aapl"}}
    handle_update(msg, s, tg, ALLOWED, validate=lambda t: True)
    assert s.list_tickers() == ["MSFT"]
    assert s.kv_get(f"awaiting:{OWNER}") is None  # flag cleared


def test_legacy_delete_callback_still_removes(tmp_path):
    s = _store(tmp_path)
    tg = FakeTG()
    cb = {"update_id": 20, "callback_query": {"id": "cb2", "data": "del:AAPL",
          "message": {"chat": {"id": OWNER}}}}
    handle_update(cb, s, tg, ALLOWED, validate=lambda t: True)
    assert s.list_tickers() == ["MSFT"]
    assert tg.callbacks and tg.callbacks[0][0] == "cb2"
