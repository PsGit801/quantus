"""Always-on Telegram listener — long-polls for instant watchlist control.

Unlike `ddbot.sync` (a cron one-shot), this runs continuously: it holds a long-poll
connection to Telegram so button taps and commands are handled the moment they arrive,
answering callback queries instantly (no stuck spinner). Reuses `sync.handle_update`.

IMPORTANT: only one process may call getUpdates for a given bot token. Do NOT run this
alongside the `ddbot-watchlist-sync` cron — delete that job first, or Telegram returns
"Conflict" errors. The daily scanner is fine (it only uses sendMessage).

Run via `scripts/listen.sh`, kept alive by launchd (see deploy/).
"""

from __future__ import annotations

import argparse
import logging
import time

from .config import Secrets, load_config
from .run import _load_dotenv
from .state.store import PatternStore
from .sync import TelegramClient, handle_update, owner_allow_set

log = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Always-on Telegram watchlist listener")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--poll-timeout", type=int, default=30, help="long-poll seconds")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    _load_dotenv(args.env_file)
    cfg = load_config(args.config)
    secrets = Secrets.from_env()
    if not secrets.telegram_token:
        print("TELEGRAM_TOKEN not set; nothing to listen for")
        return 1

    allowed = owner_allow_set(secrets)
    store = PatternStore(cfg.db_path)
    store.seed_watchlist(cfg.tickers)
    tg = TelegramClient(secrets.telegram_token, timeout=args.poll_timeout + 10)

    saved = store.kv_get("tg_offset")
    offset = int(saved) + 1 if saved else None
    log.info("listening (long-poll %ss); authorized chats=%s", args.poll_timeout, allowed or "NONE")

    while True:
        try:
            updates = tg.get_updates(offset, long_poll=args.poll_timeout)
        except Exception as exc:  # transient network / API blip — back off and retry
            log.warning("getUpdates error: %s; retrying in 3s", exc)
            time.sleep(3)
            continue

        for u in updates:
            try:
                uid = handle_update(u, store, tg, allowed)
            except Exception as exc:  # isolate one bad update
                log.exception("error handling update: %s", exc)
                uid = u.get("update_id")
            if uid is not None:
                offset = uid + 1
                store.kv_set("tg_offset", str(uid))


if __name__ == "__main__":
    import sys

    sys.exit(main())
