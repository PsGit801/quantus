"""Signal-outcome report — did the live alerts play out like the backtest?

Reads every alert the bot fired (from the SQLite `patterns` table), replays each
signal's forward price to label it win / loss / timeout / open, and prints live results
next to the backtest expectancy. Read-only: never sends, never mutates state.

    python -m ddbot.journal                # all fired signals
    python -m ddbot.journal --since 2026-07-03   # only post-go-live
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
from dataclasses import dataclass
from datetime import date

import pandas as pd

from .backtest.engine import BacktestConfig
from .backtest.metrics import summarize
from .config import load_config
from .data.yahoo import YahooDataProvider
from .patterns.base import DoubleBottom
from .state.store import PatternStore

# Backtest reference (from docs/README) to compare live results against.
BACKTEST_REF = "backtest daily ~75% win, +0.12R/trade, PF ~1.5"


@dataclass(frozen=True)
class Outcome:
    ticker: str
    timeframe: str
    confirm_date: date
    entry: float
    stop: float
    target: float
    status: str          # win | loss | timeout | open | unknown
    r_multiple: float    # realized, or unrealized (if open)
    price: float         # exit price, or latest close (if open)
    bars: int            # bars held / bars open so far
    unrealized: bool


def _dates(df: pd.DataFrame) -> list[date]:
    return [ts.date() if hasattr(ts, "date") else ts for ts in df.index]


def evaluate(df: pd.DataFrame, p: DoubleBottom, bt: BacktestConfig) -> Outcome:
    """Label a fired signal by replaying forward prices from its confirmation bar."""
    entry = p.confirm_close
    stop = p.stop_reference
    risk = entry - stop
    target = p.neckline + (p.neckline - stop)  # measured move

    def out(status, price, bars, unreal):
        r = (price - entry) / risk if risk > 0 else 0.0
        return Outcome(p.ticker, p.timeframe, p.confirm_date, round(entry, 2), round(stop, 2),
                       round(target, 2), status, round(r, 3), round(price, 2), bars, unreal)

    if df.empty or risk <= 0:
        return out("unknown", entry, 0, False)
    dts = _dates(df)
    if p.confirm_date not in dts:
        return out("unknown", entry, 0, False)  # data window doesn't reach this signal

    j = dts.index(p.confirm_date)
    highs = df["high"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float)
    closes = df["close"].to_numpy(dtype=float)
    end = len(df) - 1

    for i in range(j + 1, min(end, j + bt.max_hold_bars) + 1):
        if lows[i] <= stop:  # stop-first if both hit (conservative)
            return out("loss", stop, i - j, False)
        if highs[i] >= target:
            return out("win", target, i - j, False)

    bars = end - j
    if bars <= 0:
        return out("open", entry, 0, True)  # just confirmed, no forward bars yet
    if bars >= bt.max_hold_bars:
        return out("timeout", float(closes[end]), bars, False)
    # Unresolved and still within the holding window -> OPEN (unrealized)
    return out("open", float(closes[end]), bars, True)


def build(store: PatternStore, provider: YahooDataProvider, bt: BacktestConfig,
          since: date | None, history: dict[str, int]) -> list[Outcome]:
    signals = store.alerted_patterns()
    if since:
        signals = [s for s in signals if s.confirm_date and s.confirm_date >= since]

    # Fetch each (ticker, timeframe) once.
    cache: dict[tuple, pd.DataFrame] = {}
    outcomes = []
    for s in signals:
        key = (s.ticker, s.timeframe)
        if key not in cache:
            cache[key] = provider.get_ohlcv(s.ticker, s.timeframe, history.get(s.timeframe, 750))
        outcomes.append(evaluate(cache[key], s, bt))
    return outcomes


def format_report(outcomes: list[Outcome]) -> str:
    if not outcomes:
        return "No fired signals found (nothing to report yet)."

    hdr = f"{'Ticker':<7}{'TF':<5}{'Confirmed':<12}{'Status':<9}{'R':>7}{'Entry':>9}{'Now/Exit':>10}{'Bars':>6}"
    lines = [hdr, "-" * len(hdr)]
    for o in sorted(outcomes, key=lambda x: (x.confirm_date or date.min, x.ticker)):
        r = f"{o.r_multiple:+.2f}" + ("*" if o.unrealized else "")
        lines.append(
            f"{o.ticker:<7}{o.timeframe:<5}{str(o.confirm_date):<12}{o.status:<9}"
            f"{r:>7}{o.entry:>9.2f}{o.price:>10.2f}{o.bars:>6}"
        )

    resolved = [o for o in outcomes if o.status in ("win", "loss", "timeout")]
    open_ = [o for o in outcomes if o.status == "open"]
    lines.append("-" * len(hdr))
    lines.append(f"{len(outcomes)} fired  |  {len(resolved)} resolved  |  {len(open_)} open  "
                 f"|  {sum(1 for o in outcomes if o.status=='unknown')} unknown")

    if resolved:
        # Reuse the backtest metric summarizer via lightweight Trade-like shims.
        from .backtest.engine import Trade
        shim = [Trade(o.ticker, o.timeframe, o.confirm_date, o.entry, o.stop, o.target,
                      o.confirm_date, o.price, o.r_multiple, 0.0, o.bars, o.status) for o in resolved]
        s = summarize(shim)
        pf = "inf" if s.profit_factor == float("inf") else f"{s.profit_factor:.2f}"
        lines.append(f"LIVE (resolved): win {s.win_rate:.0f}%  |  avg {s.avg_r:+.2f}R  |  "
                     f"total {s.total_r:+.1f}R  |  PF {pf}")
    if open_:
        unreal = sum(o.r_multiple for o in open_)
        lines.append(f"OPEN (unrealized): {len(open_)} positions, {unreal:+.1f}R marked-to-market  (* = unrealized)")
    lines.append(f"Reference: {BACKTEST_REF}")
    lines.append("Note: indicative — ignores slippage/commissions; small samples aren't conclusive.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Signal-outcome report for fired alerts")
    p.add_argument("--config", default="config/config.yaml")
    p.add_argument("--since", help="only signals confirmed on/after this date (YYYY-MM-DD)")
    p.add_argument("--max-hold", type=int, default=60)
    p.add_argument("--history-bars", type=int, default=750, help="daily bars to fetch (weekly uses ~half)")
    p.add_argument("--csv", help="write outcomes to this CSV path")
    args = p.parse_args(argv)

    cfg = load_config(args.config)
    store = PatternStore(cfg.db_path)
    provider = YahooDataProvider(drop_forming_bar=cfg.drop_forming_bar)
    bt = BacktestConfig(max_hold_bars=args.max_hold)
    since = date.fromisoformat(args.since) if args.since else None
    history = {"1d": args.history_bars, "1wk": max(args.history_bars // 2, 300)}

    try:
        outcomes = build(store, provider, bt, since, history)
    finally:
        store.close()

    print("\nSignal journal" + (f" (since {since})" if since else "") + "\n")
    print(format_report(outcomes))
    print()

    if args.csv and outcomes:
        fields = [f.name for f in dataclasses.fields(outcomes[0])]
        with open(args.csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for o in outcomes:
                w.writerow(dataclasses.asdict(o))
        print(f"wrote {len(outcomes)} rows to {args.csv}")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
