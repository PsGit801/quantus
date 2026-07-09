"""Walk-forward backtest of the double-bottom strategy.

For each bar it runs the *exact* live detector on the trailing window the bot would
have seen, so there's no look-ahead: a trade is entered the first time a pattern
CONFIRMS, then simulated forward with a stop and target. This mirrors production
(`engine.py` + `store`) so backtested edge reflects what the live bot would do.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from ..config import DetectionConfig
from ..patterns.base import DoubleBottom, PatternState
from ..patterns.double_bottom import check_confirmation, detect


@dataclass(frozen=True)
class BacktestConfig:
    target: str = "neckline"       # "neckline" | "measured_move" | "r_multiple"
    r_target: float = 2.0          # used when target == "r_multiple"
    max_hold_bars: int = 60


@dataclass(frozen=True)
class Trade:
    ticker: str
    timeframe: str
    entry_date: date
    entry: float
    stop: float
    target: float
    exit_date: date
    exit: float
    r_multiple: float
    return_pct: float
    bars_held: int
    outcome: str  # "win" | "loss" | "timeout"


def _dates(df: pd.DataFrame) -> list[date]:
    return [ts.date() if hasattr(ts, "date") else ts for ts in df.index]


def find_signals(
    df: pd.DataFrame, ticker: str, timeframe: str, cfg: DetectionConfig
) -> list[DoubleBottom]:
    """Walk forward and return each pattern's first confirmation (no look-ahead)."""
    pending: dict[str, DoubleBottom] = {}
    seen: set[str] = set()
    confirmed: list[DoubleBottom] = []

    n = len(df)
    for t in range(cfg.lookback_bars, n):
        window = df.iloc[: t + 1]

        for p in detect(window, ticker, timeframe, cfg):
            if p.pattern_id not in seen and p.pattern_id not in pending:
                pending[p.pattern_id] = p

        for pid in list(pending):
            res = check_confirmation(pending[pid], window, cfg)
            if res.state is PatternState.CONFIRMED:
                confirmed.append(res)
                seen.add(pid)
                del pending[pid]
            elif res.state is PatternState.INVALIDATED:
                seen.add(pid)
                del pending[pid]

    # Drop cross-window duplicates: same breakout bar + ~same neckline = one trade.
    unique: dict[tuple, DoubleBottom] = {}
    for p in confirmed:
        key = (p.confirm_date, round(p.neckline, 2))
        unique.setdefault(key, p)
    return sorted(unique.values(), key=lambda p: p.confirm_date)


def _target_price(p: DoubleBottom, entry: float, stop: float, bt: BacktestConfig) -> float:
    if bt.target == "r_multiple":
        return entry + bt.r_target * (entry - stop)
    if bt.target == "measured_move":
        return p.neckline + (p.neckline - stop)
    # neckline (default): first resistance for a below-neckline reclaim entry
    return p.neckline


def simulate_trade(
    df: pd.DataFrame, p: DoubleBottom, bt: BacktestConfig
) -> Trade | None:
    """Simulate one trade forward from its confirmation bar. None if untradeable."""
    dates = _dates(df)
    if p.confirm_date not in dates:
        return None
    j = dates.index(p.confirm_date)

    entry = p.confirm_close
    stop = p.stop_reference
    risk = entry - stop
    target = _target_price(p, entry, stop, bt)
    if risk <= 0 or target <= entry:
        return None  # degenerate risk/reward — skip

    highs = df["high"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float)
    closes = df["close"].to_numpy(dtype=float)

    end = min(len(df) - 1, j + bt.max_hold_bars)
    for i in range(j + 1, end + 1):
        if lows[i] <= stop:  # stop-first if both hit in one bar (conservative)
            exit_price, outcome = stop, "loss"
        elif highs[i] >= target:
            exit_price, outcome = target, "win"
        else:
            continue
        return _make_trade(p, entry, stop, target, dates[i], exit_price, i - j, outcome)

    # Time exit at the last available bar's close.
    exit_price = float(closes[end])
    outcome = "win" if exit_price >= entry else "loss"
    return _make_trade(p, entry, stop, target, dates[end], exit_price, end - j, "timeout" if end - j >= bt.max_hold_bars else outcome)


def _make_trade(p, entry, stop, target, exit_date, exit_price, bars, outcome) -> Trade:
    risk = entry - stop
    return Trade(
        ticker=p.ticker,
        timeframe=p.timeframe,
        entry_date=p.confirm_date,
        entry=round(entry, 4),
        stop=round(stop, 4),
        target=round(target, 4),
        exit_date=exit_date,
        exit=round(exit_price, 4),
        r_multiple=round((exit_price - entry) / risk, 3),
        return_pct=round((exit_price - entry) / entry * 100, 3),
        bars_held=bars,
        outcome=outcome,
    )


def backtest_ticker(
    df: pd.DataFrame,
    ticker: str,
    timeframe: str,
    cfg: DetectionConfig,
    bt: BacktestConfig,
    mtf_filter=None,
) -> list[Trade]:
    """Backtest one ticker. `mtf_filter(confirm_date)->bool`, if given, gates signals
    (multi-timeframe confirmation) so the backtest matches live behavior."""
    if df.empty:
        return []
    trades = []
    for sig in find_signals(df, ticker, timeframe, cfg):
        if mtf_filter is not None and not mtf_filter(sig.confirm_date):
            continue
        tr = simulate_trade(df, sig, bt)
        if tr is not None:
            trades.append(tr)
    return trades
