"""Weekly digest — pushes a compact live-results + health summary to Telegram/Discord.

Builds the signal journal (how fired alerts are playing out) over a recent window, adds a
health line from the scan/listener heartbeats, and sends one short message. Meant to run on a
weekly cron; read-only w.r.t. strategy state.

    python -m ddbot.digest --dry-run       # print instead of send
    python -m ddbot.digest --days 7        # summarise the last 7 days (default)
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta

from .backtest.engine import BacktestConfig, Trade
from .backtest.metrics import summarize
from .config import Secrets, load_config
from .data.yahoo import YahooDataProvider
from .journal import BACKTEST_REF, Outcome, build
from .run import _build_alerter, _load_dotenv
from .state.store import PatternStore

SCAN_STALE_DAYS = 2      # daily scan runs every day; older than this = likely down
LISTEN_STALE_DAYS = 1    # listener heartbeats every poll cycle when alive


def _age_days(iso: str | None, today: date) -> int | None:
    if not iso:
        return None
    try:
        return (today - date.fromisoformat(iso[:10])).days
    except ValueError:
        return None


def health_line(store: PatternStore, today: date) -> str:
    """One-line health check from the scan/listener heartbeats + watchlist size."""
    parts = []

    scan = _age_days(store.kv_get("last_scan_at"), today)
    if scan is None:
        parts.append("⚠️ scan: never run")
    elif scan > SCAN_STALE_DAYS:
        parts.append(f"⚠️ scan {scan}d stale")
    else:
        parts.append("scan ok" if scan == 0 else f"scan {scan}d ago")

    listen = _age_days(store.kv_get("last_listen_at"), today)
    if listen is None:
        parts.append("⚠️ listener: no heartbeat")
    elif listen > LISTEN_STALE_DAYS:
        parts.append(f"⚠️ listener {listen}d stale")
    else:
        parts.append("listener ok")

    parts.append(f"watchlist {len(store.list_tickers())}")
    return "🩺 Health: " + " · ".join(parts)


def format_digest(outcomes: list[Outcome], health: str, since: date | None) -> str:
    scope = f"since {since}" if since else "all time"
    lines = ["📊 *Quantus digest*", health, ""]

    if not outcomes:
        lines.append(f"No alerts fired ({scope}).")
        lines.append("")
        lines.append(f"_Backtest ref: {BACKTEST_REF}._")
        return "\n".join(lines)

    resolved = [o for o in outcomes if o.status in ("win", "loss", "timeout")]
    open_ = [o for o in outcomes if o.status == "open"]
    lines.append(f"*{len(outcomes)} alerts* ({scope}) — {len(resolved)} resolved, {len(open_)} open")

    if resolved:
        shim = [Trade(o.ticker, o.timeframe, o.confirm_date, o.entry, o.stop, o.target,
                      o.confirm_date, o.price, o.r_multiple, 0.0, o.bars, o.status) for o in resolved]
        s = summarize(shim)
        pf = "∞" if s.profit_factor == float("inf") else f"{s.profit_factor:.2f}"
        lines.append(f"Resolved: win {s.win_rate:.0f}% · avg {s.avg_r:+.2f}R · "
                     f"total {s.total_r:+.1f}R · PF {pf}")
    if open_:
        unreal = sum(o.r_multiple for o in open_)
        lines.append(f"Open: {len(open_)} positions, {unreal:+.1f}R unrealized")

    lines.append("")
    lines.append(f"_Backtest ref: {BACKTEST_REF}. Discretionary — review each chart; "
                 "small samples aren't conclusive._")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Weekly live-results + health digest")
    p.add_argument("--config", default="config/config.yaml")
    p.add_argument("--env-file", default=".env")
    p.add_argument("--days", type=int, default=7, help="summarise the last N days (0 = all time)")
    p.add_argument("--since", help="override --days with an explicit YYYY-MM-DD")
    p.add_argument("--max-hold", type=int, default=60)
    p.add_argument("--history-bars", type=int, default=750)
    p.add_argument("--dry-run", action="store_true", help="print the digest instead of sending it")
    args = p.parse_args(argv)

    _load_dotenv(args.env_file)
    cfg = load_config(args.config)
    store = PatternStore(cfg.db_path)
    provider = YahooDataProvider(drop_forming_bar=cfg.drop_forming_bar)
    bt = BacktestConfig(max_hold_bars=args.max_hold)

    today = date.today()
    if args.since:
        since = date.fromisoformat(args.since)
    elif args.days > 0:
        since = today - timedelta(days=args.days)
    else:
        since = None
    history = {"1d": args.history_bars, "1wk": max(args.history_bars // 2, 300)}

    try:
        outcomes = build(store, provider, bt, since, history)
        msg = format_digest(outcomes, health_line(store, today), since)
    finally:
        store.close()

    if args.dry_run:
        print(msg)
        return 0

    alerter = _build_alerter(Secrets.from_env())
    alerter.send(msg)
    print("digest sent")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
