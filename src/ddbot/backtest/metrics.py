"""Aggregate backtest trades into performance statistics."""

from __future__ import annotations

from dataclasses import dataclass

from .engine import Trade


@dataclass(frozen=True)
class Stats:
    trades: int
    wins: int
    losses: int
    win_rate: float          # %
    avg_r: float             # expectancy per trade (R)
    total_r: float
    profit_factor: float     # gross win R / gross loss R (inf if no losses)
    max_drawdown_r: float    # worst peak-to-trough on the cumulative-R curve
    avg_bars_held: float
    avg_return_pct: float


@dataclass(frozen=True)
class EquityStats:
    start_equity: float
    final_equity: float
    total_return_pct: float
    cagr_pct: float
    max_drawdown_pct: float
    trades: int


def equity_curve(trades: list[Trade], start_equity: float, risk_pct: float) -> EquityStats:
    """Fixed-fractional $ equity via sequential compounding on R (exit-date order).

    Each trade risks `risk_pct` of *current* equity, so equity *= (1 + risk_pct * R).
    Simplification: treats trades sequentially (ignores concurrent-position capital
    competition); good enough for a first-order dollar picture.
    """
    if not trades:
        return EquityStats(start_equity, start_equity, 0.0, 0.0, 0.0, 0)

    ordered = sorted(trades, key=lambda t: t.exit_date)
    eq = start_equity
    peak = start_equity
    max_dd = 0.0
    for t in ordered:
        eq *= (1 + risk_pct * t.r_multiple)
        peak = max(peak, eq)
        if peak > 0:
            max_dd = max(max_dd, (peak - eq) / peak)

    total_return = eq / start_equity - 1
    first = min(t.entry_date for t in ordered)
    last = max(t.exit_date for t in ordered)
    years = max((last - first).days / 365.25, 1e-9)
    cagr = (eq / start_equity) ** (1 / years) - 1 if eq > 0 else -1.0

    return EquityStats(
        start_equity=round(start_equity, 2),
        final_equity=round(eq, 2),
        total_return_pct=round(total_return * 100, 2),
        cagr_pct=round(cagr * 100, 2),
        max_drawdown_pct=round(max_dd * 100, 2),
        trades=len(ordered),
    )


def _max_drawdown_r(rs: list[float]) -> float:
    peak = 0.0
    cum = 0.0
    max_dd = 0.0
    for r in rs:
        cum += r
        peak = max(peak, cum)
        max_dd = max(max_dd, peak - cum)
    return round(max_dd, 3)


def summarize(trades: list[Trade]) -> Stats:
    n = len(trades)
    if n == 0:
        return Stats(0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    rs = [t.r_multiple for t in trades]
    wins = [t for t in trades if t.r_multiple > 0]
    losses = [t for t in trades if t.r_multiple <= 0]
    gross_win = sum(t.r_multiple for t in wins)
    gross_loss = -sum(t.r_multiple for t in losses)  # positive magnitude

    profit_factor = float("inf") if gross_loss == 0 else round(gross_win / gross_loss, 3)

    return Stats(
        trades=n,
        wins=len(wins),
        losses=len(losses),
        win_rate=round(len(wins) / n * 100, 1),
        avg_r=round(sum(rs) / n, 3),
        total_r=round(sum(rs), 3),
        profit_factor=profit_factor,
        max_drawdown_r=_max_drawdown_r(rs),
        avg_bars_held=round(sum(t.bars_held for t in trades) / n, 1),
        avg_return_pct=round(sum(t.return_pct for t in trades) / n, 3),
    )


def format_report(per_ticker: dict[str, Stats], overall: Stats) -> str:
    hdr = f"{'Ticker':<8}{'Trades':>7}{'Win%':>7}{'AvgR':>8}{'TotR':>8}{'PF':>7}{'MaxDD':>8}{'Bars':>7}"
    lines = [hdr, "-" * len(hdr)]

    def row(name: str, s: Stats) -> str:
        pf = "inf" if s.profit_factor == float("inf") else f"{s.profit_factor:.2f}"
        return (
            f"{name:<8}{s.trades:>7}{s.win_rate:>7.1f}{s.avg_r:>8.2f}"
            f"{s.total_r:>8.1f}{pf:>7}{s.max_drawdown_r:>8.1f}{s.avg_bars_held:>7.1f}"
        )

    for tk in sorted(per_ticker):
        lines.append(row(tk, per_ticker[tk]))
    lines.append("-" * len(hdr))
    lines.append(row("ALL", overall))
    return "\n".join(lines)
