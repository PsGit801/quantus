"""Telegram watchlist sync — a one-shot polled by a frequent hermes cron.

Each run asks Telegram for new messages/button taps since the last run (``getUpdates``
with a persisted offset), applies any add/remove edits to the DB watchlist, replies,
and exits. No always-on process: when nothing is pending it does effectively nothing.

Only the configured owner chat_id is honored; all other chats are ignored.
"""

from __future__ import annotations

import argparse
import logging
import re

import requests

from .config import Secrets, load_config
from .data.yahoo import validate_symbol
from .run import _load_dotenv
from .state.store import PatternStore
from .watchlist import add_symbols, parse_symbols, remove_symbols  # shared ops (DRY)

log = logging.getLogger(__name__)

CB_ADD = "add"
CB_REMOVE = "remove"
CB_DEL_PREFIX = "del:"  # legacy per-ticker buttons; still honored if tapped

WELCOME_TEXT = (
    "👋 Welcome to *Quantus* — your chart-pattern scanner.\n\n"
    "I watch your watchlist on *daily* and *weekly* timeframes and alert you here the moment a "
    "*double bottom* confirms with a bullish breakout — chart attached.\n\n"
    "Alerts arrive automatically; you don't need to do anything. 📈"
)

HELP_TEXT = (
    "*Quantus watchlist*\n"
    "/list — show tracked tickers\n"
    "/add SYMBOL [SYMBOL...] — add tickers\n"
    "/remove SYMBOL — remove a ticker"
)


# --- pure helpers (unit-tested) -------------------------------------------------

def owner_allow_set(secrets) -> set[int]:
    """Set of chat_ids permitted to control the bot (just the configured owner)."""
    ids: set[int] = set()
    if secrets.telegram_chat_id:
        try:
            ids.add(int(secrets.telegram_chat_id))
        except ValueError:
            log.warning("TELEGRAM_CHAT_ID is not an integer; no chats are authorized")
    return ids


def is_authorized(chat_id, allowed_ids) -> bool:
    try:
        return int(chat_id) in allowed_ids
    except (TypeError, ValueError):
        return False


def build_watchlist_keyboard() -> dict:
    """Fixed 2-button keyboard — scales to any watchlist size (unlike per-ticker rows)."""
    return {
        "inline_keyboard": [[
            {"text": "➕ Add", "callback_data": CB_ADD},
            {"text": "➖ Remove", "callback_data": CB_REMOVE},
        ]]
    }


def format_watchlist(tickers: list[str]) -> str:
    if not tickers:
        return "Your watchlist is empty. Tap ➕ Add ticker or use /add SYMBOL."
    body = "\n".join(f"• {t}" for t in tickers)
    return f"📋 *Watchlist* ({len(tickers)})\n{body}"


# --- Telegram client ------------------------------------------------------------

class TelegramClient:
    def __init__(self, token: str, timeout: float = 15.0):
        self.base = f"https://api.telegram.org/bot{token}"
        self.timeout = timeout

    def get_updates(self, offset: int | None = None, long_poll: int = 0) -> list[dict]:
        params: dict = {"timeout": long_poll}
        if offset is not None:
            params["offset"] = offset
        # For long polling the HTTP read must outlast Telegram's hold.
        req_timeout = long_poll + 10 if long_poll else self.timeout
        r = requests.get(self.base + "/getUpdates", params=params, timeout=req_timeout)
        r.raise_for_status()
        return r.json().get("result", [])

    def send_message(self, chat_id, text, reply_markup: dict | None = None) -> None:
        payload: dict = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        r = requests.post(self.base + "/sendMessage", json=payload, timeout=self.timeout)
        r.raise_for_status()

    def answer_callback(self, callback_id, text: str | None = None) -> None:
        payload: dict = {"callback_query_id": callback_id}
        if text:
            payload["text"] = text
        requests.post(self.base + "/answerCallbackQuery", json=payload, timeout=self.timeout)


# --- dispatch (unit-tested with a fake client) ----------------------------------

def _send_list(store: PatternStore, tg, chat_id) -> None:
    tg.send_message(chat_id, format_watchlist(store.list_tickers()), build_watchlist_keyboard())


def _do_add(raw: str, store: PatternStore, tg, chat_id, validate) -> None:
    syms = parse_symbols(raw)
    if not syms:
        tg.send_message(chat_id, "No valid symbols found. Try e.g. `PLTR` or `PLTR, COIN`.")
        return
    added, dupes, rejected = add_symbols(store, syms, validate)
    parts = []
    if added:
        parts.append("✅ Added: " + ", ".join(added))
    if dupes:
        parts.append("• Already tracked: " + ", ".join(dupes))
    if rejected:
        parts.append("❌ Not found on Yahoo: " + ", ".join(rejected))
    tg.send_message(chat_id, "\n".join(parts))
    _send_list(store, tg, chat_id)


def _do_remove(raw: str, store: PatternStore, tg, chat_id) -> None:
    syms = parse_symbols(raw)
    if not syms:
        tg.send_message(chat_id, "Usage: /remove SYMBOL")
        return
    removed = remove_symbols(store, syms)
    tg.send_message(chat_id, "🗑 Removed: " + ", ".join(removed) if removed else "Nothing removed.")
    _send_list(store, tg, chat_id)


def handle_update(update: dict, store: PatternStore, tg, allowed_ids, validate=validate_symbol) -> int | None:
    """Process one Telegram update. Returns its update_id (for offset tracking)."""
    uid = update.get("update_id")

    # Button tap
    cq = update.get("callback_query")
    if cq:
        chat_id = (cq.get("message") or {}).get("chat", {}).get("id")
        if not is_authorized(chat_id, allowed_ids):
            return uid
        data = cq.get("data", "")
        if data == CB_ADD:
            store.kv_set(f"awaiting:{chat_id}", "add")
            tg.answer_callback(cq["id"])
            tg.send_message(chat_id, "Send the ticker symbol(s) to *add* (e.g. `PLTR` or `PLTR, COIN`).")
        elif data == CB_REMOVE:
            store.kv_set(f"awaiting:{chat_id}", "remove")
            tg.answer_callback(cq["id"])
            tg.send_message(chat_id, "Send the ticker symbol(s) to *remove* (e.g. `TSLA`).")
        elif data.startswith(CB_DEL_PREFIX):
            sym = data[len(CB_DEL_PREFIX):]
            removed = store.remove_ticker(sym)
            tg.answer_callback(cq["id"], f"Removed {sym}" if removed else f"{sym} not tracked")
            _send_list(store, tg, chat_id)
        else:
            tg.answer_callback(cq["id"])
        return uid

    # Text message
    msg = update.get("message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    text = (msg.get("text") or "").strip()
    if chat_id is None or not text or not is_authorized(chat_id, allowed_ids):
        return uid

    awaiting_key = f"awaiting:{chat_id}"
    low = text.lower()
    if low.startswith("/start"):
        store.kv_set(awaiting_key, None)
        tg.send_message(chat_id, WELCOME_TEXT)
    elif low.startswith("/help"):
        store.kv_set(awaiting_key, None)
        tg.send_message(chat_id, HELP_TEXT)
        _send_list(store, tg, chat_id)
    elif low.startswith("/list") or low.startswith("/tickers"):
        store.kv_set(awaiting_key, None)
        _send_list(store, tg, chat_id)
    elif low.startswith("/add"):
        store.kv_set(awaiting_key, None)
        _do_add(text[4:], store, tg, chat_id, validate)
    elif low.startswith("/remove") or low.startswith("/rm"):
        store.kv_set(awaiting_key, None)
        _do_remove(re.sub(r"^/\w+", "", text), store, tg, chat_id)
    elif store.kv_get(awaiting_key) == "remove":
        store.kv_set(awaiting_key, None)
        _do_remove(text, store, tg, chat_id)
    elif store.kv_get(awaiting_key) == "add":
        store.kv_set(awaiting_key, None)
        _do_add(text, store, tg, chat_id, validate)
    else:
        tg.send_message(chat_id, "Send /list to manage your watchlist, or /help.")
    return uid


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Telegram watchlist sync (one-shot)")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    _load_dotenv(args.env_file)
    cfg = load_config(args.config)
    secrets = Secrets.from_env()
    if not secrets.telegram_token:
        print("TELEGRAM_TOKEN not set; nothing to poll")
        return 0

    allowed = owner_allow_set(secrets)

    store = PatternStore(cfg.db_path)
    store.seed_watchlist(cfg.tickers)
    tg = TelegramClient(secrets.telegram_token)

    saved = store.kv_get("tg_offset")
    offset = int(saved) + 1 if saved else None
    try:
        updates = tg.get_updates(offset)
    except Exception as exc:
        log.error("getUpdates failed: %s", exc)
        store.close()
        return 1

    max_uid = None
    for u in updates:
        try:
            uid = handle_update(u, store, tg, allowed)
        except Exception as exc:
            log.exception("error handling update: %s", exc)
            uid = u.get("update_id")
        if uid is not None:
            max_uid = uid if max_uid is None else max(max_uid, uid)

    if max_uid is not None:
        store.kv_set("tg_offset", str(max_uid))
    store.close()
    print(f"sync: processed {len(updates)} update(s)")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
