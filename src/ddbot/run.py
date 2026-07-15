"""CLI entrypoint. hermes invokes this once per day: ``python -m ddbot.run``."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from .alerts.composite import CompositeAlerter
from .alerts.discord import DiscordAlerter
from .alerts.telegram import TelegramAlerter
from .config import Secrets, load_config
from .data.yahoo import YahooDataProvider
from .engine import Engine
from .state.store import PatternStore


def _load_dotenv(path: str | Path = ".env") -> None:
    """Populate os.environ from a .env file (zero-dependency).

    Cron/hermes launch with a bare environment, so secrets defined only in .env would
    otherwise be missing. Existing env vars always win, so hermes can still override.
    """
    p = Path(path)
    if not p.is_file():
        return
    for raw in p.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _build_alerter(secrets: Secrets) -> CompositeAlerter:
    channels = []
    if secrets.telegram_token and secrets.telegram_chat_id:
        channels.append(TelegramAlerter(secrets.telegram_token, secrets.telegram_chat_id))
    if secrets.discord_webhook_url:
        channels.append(DiscordAlerter(secrets.discord_webhook_url))
    return CompositeAlerter(channels)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Double-bottom detection & alert bot")
    parser.add_argument("--config", default="config/config.yaml", help="path to config YAML")
    parser.add_argument(
        "--dry-run", action="store_true", help="print alerts instead of sending them"
    )
    parser.add_argument("--env-file", default=".env", help="path to the .env secrets file")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    _load_dotenv(args.env_file)
    cfg = load_config(args.config)
    provider = YahooDataProvider(drop_forming_bar=cfg.drop_forming_bar)
    store = PatternStore(cfg.db_path)
    alerter = None if args.dry_run else _build_alerter(Secrets.from_env())

    engine = Engine(cfg, provider, store, alerter, dry_run=args.dry_run)
    try:
        fired = engine.run()
    except Exception as exc:
        # A fatal (whole-run) failure would otherwise be silent — make it visible.
        if alerter is not None:
            try:
                alerter.send(f"⚠️ Quantus daily scan failed: {type(exc).__name__}: {exc}")
            except Exception:  # never let the failure-notifier mask the original error
                pass
        raise
    finally:
        store.close()

    print(f"done: {fired} alert(s) fired")
    return 0


if __name__ == "__main__":
    sys.exit(main())
