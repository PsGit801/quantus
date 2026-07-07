"""Watchlist management — deterministic ops + a small CLI.

The watchlist lives in the SQLite `watchlist` table. This module is the single place
that mutates it, so both the Telegram sync (`ddbot.sync`) and natural-language edits
driven by hermes/qwen go through the same validated logic:

    python -m ddbot.watchlist list
    python -m ddbot.watchlist add PLTR COIN
    python -m ddbot.watchlist remove TSLA
"""

from __future__ import annotations

import argparse
import re

from .config import load_config
from .data.yahoo import normalize_symbol, validate_symbol
from .state.store import PatternStore


def parse_symbols(raw: str) -> list[str]:
    """Split free text into a de-duplicated list of normalized, valid-shape symbols."""
    out: list[str] = []
    for tok in re.split(r"[,\s]+", (raw or "").strip()):
        if not tok:
            continue
        s = normalize_symbol(tok)
        if s and s not in out:
            out.append(s)
    return out


def add_symbols(store: PatternStore, symbols: list[str], validate=validate_symbol):
    """Add validated symbols. Returns (added, dupes, rejected)."""
    current = set(store.list_tickers())
    added, dupes, rejected = [], [], []
    for s in symbols:
        if s in current:
            dupes.append(s)
        elif not validate(s):
            rejected.append(s)
        elif store.add_ticker(s):
            added.append(s)
            current.add(s)
    return added, dupes, rejected


def remove_symbols(store: PatternStore, symbols: list[str]) -> list[str]:
    """Remove symbols that are present. Returns the list actually removed."""
    return [s for s in symbols if store.remove_ticker(s)]


def _cmd_list(store) -> str:
    tickers = store.list_tickers()
    return "Watchlist (%d): %s" % (len(tickers), ", ".join(tickers) or "(empty)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage the ddbot watchlist")
    parser.add_argument("--config", default="config/config.yaml")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    p_add = sub.add_parser("add")
    p_add.add_argument("symbols", nargs="+")
    p_rm = sub.add_parser("remove")
    p_rm.add_argument("symbols", nargs="+")
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    store = PatternStore(cfg.db_path)
    store.seed_watchlist(cfg.tickers)

    try:
        if args.command == "list":
            print(_cmd_list(store))
        elif args.command == "add":
            syms = parse_symbols(" ".join(args.symbols))
            added, dupes, rejected = add_symbols(store, syms)
            if added:
                print("Added:", ", ".join(added))
            if dupes:
                print("Already tracked:", ", ".join(dupes))
            if rejected:
                print("Rejected (not found on Yahoo):", ", ".join(rejected))
            print(_cmd_list(store))
        elif args.command == "remove":
            syms = parse_symbols(" ".join(args.symbols))
            removed = remove_symbols(store, syms)
            print("Removed:", ", ".join(removed) if removed else "(nothing)")
            print(_cmd_list(store))
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
