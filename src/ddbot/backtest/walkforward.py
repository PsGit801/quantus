"""Rolling walk-forward analysis: is the edge stable across time, or one lucky window?

The main backtest report summarizes a single config over the *entire* history with no
holdout. That can't tell overfit-to-one-period from a genuine, persistent edge. This
module slices the resulting trades by entry date into sequential calendar folds and
summarizes each independently, plus an anchored "held-out newest X%" split. If most
folds — and the held-out tail — stay positive, the edge held out of sample.

It reuses the exact same `summarize()` the live journal uses, so fold numbers are
directly comparable to live results. No detection or simulation logic lives here.
"""

from __future__ import annotations

from datetime import date, timedelta
from statistics import median

from .engine import Trade
from .metrics import Stats, summarize


def rolling_folds(trades: list[Trade], n_folds: int) -> list[tuple[str, list[Trade]]]:
    """Partition trades into `n_folds` contiguous, equal-length calendar windows by entry date.

    Generalizes `sweep.split_trades` from one cutoff to N. Windows are half-open
    [lo, hi) except the last, which is inclusive so the final trade lands somewhere.
    Empty folds are kept (labelled) so a barren stretch is visible rather than hidden.
    Each label is "YYYY-MM-DD…YYYY-MM-DD" (the window bounds).
    """
    if n_folds < 1:
        raise ValueError(f"n_folds must be >= 1, got {n_folds}")
    if not trades:
        return []

    ordered = sorted(trades, key=lambda t: t.entry_date)
    first = ordered[0].entry_date
    last = ordered[-1].entry_date
    total_days = (last - first).days

    # Window boundaries as calendar dates: bounds[0] == first, bounds[n] == last.
    bounds: list[date] = [
        first + timedelta(days=round(total_days * i / n_folds)) for i in range(n_folds + 1)
    ]

    buckets: list[list[Trade]] = [[] for _ in range(n_folds)]
    for t in ordered:
        buckets[_fold_of(t.entry_date, bounds)].append(t)

    return [(f"{bounds[i]}…{bounds[i + 1]}", buckets[i]) for i in range(n_folds)]


def _fold_of(entry: date, bounds: list[date]) -> int:
    """Index i such that bounds[i] <= entry <= bounds[i+1] (last window inclusive)."""
    for i in range(len(bounds) - 2):
        if entry < bounds[i + 1]:
            return i
    return len(bounds) - 2


def anchored_oos(trades: list[Trade], oos_fraction: float) -> tuple[list[Trade], list[Trade]]:
    """Split into (train = older, test = newest `oos_fraction` of trades) by entry date.

    Count-based on the pooled, entry-date-sorted trades — a single held-out tail to read
    alongside the rolling folds. Mirrors the newest-fraction intent of the sweep's OOS.
    """
    if not 0.0 < oos_fraction < 1.0:
        raise ValueError(f"oos_fraction must be in (0, 1), got {oos_fraction}")
    if not trades:
        return [], []
    ordered = sorted(trades, key=lambda t: t.entry_date)
    cut = int(len(ordered) * (1 - oos_fraction))
    cut = min(max(cut, 0), len(ordered))
    return ordered[:cut], ordered[cut:]


def walk_forward_report(
    folds: list[tuple[str, list[Trade]]],
    overall: Stats,
    min_trades: int,
    anchored: tuple[list[Trade], list[Trade]] | None = None,
) -> str:
    """Per-fold table + a stability verdict; optional anchored held-out-tail line."""
    hdr = f"{'Fold (entry-date window)':<25}{'Trades':>7}{'Win%':>7}{'AvgR':>8}{'TotR':>8}{'PF':>7}{'MaxDD':>8}{'':>6}"
    lines = ["Walk-forward — the same config sliced into sequential time windows:", "", hdr, "-" * len(hdr)]

    def pf(x: float) -> str:
        return "inf" if x == float("inf") else f"{x:.2f}"

    fold_avg_rs: list[float] = []
    for label, trades in folds:
        s = summarize(trades)
        flag = "" if s.trades == 0 else ("LOW" if s.trades < min_trades else "ok")
        if s.trades == 0:
            flag = "empty"
        else:
            fold_avg_rs.append(s.avg_r)
        lines.append(
            f"{label:<25}{s.trades:>7}{s.win_rate:>7.1f}{s.avg_r:>8.2f}"
            f"{s.total_r:>8.1f}{pf(s.profit_factor):>7}{s.max_drawdown_r:>8.1f}{flag:>6}"
        )

    lines.append("-" * len(hdr))
    lines.append(
        f"{'ALL':<25}{overall.trades:>7}{overall.win_rate:>7.1f}{overall.avg_r:>8.2f}"
        f"{overall.total_r:>8.1f}{pf(overall.profit_factor):>7}{overall.max_drawdown_r:>8.1f}{'':>6}"
    )
    lines.append("")

    # Stability verdict over folds that actually have trades.
    if fold_avg_rs:
        positive = sum(1 for r in fold_avg_rs if r > 0)
        n = len(fold_avg_rs)
        lines.append(
            f"Stability: {positive}/{n} folds with trades are positive (avg R > 0)  |  "
            f"worst fold avg R {min(fold_avg_rs):+.2f}  |  median {median(fold_avg_rs):+.2f}"
        )
    else:
        lines.append("Stability: no folds contained trades.")

    if anchored is not None:
        train, test = anchored
        ts = summarize(test)
        lines.append(
            f"Held-out newest slice: {ts.trades} trades  |  win {ts.win_rate:.0f}%  |  "
            f"avg {ts.avg_r:+.2f}R  |  PF {pf(ts.profit_factor)}  "
            f"(train had {len(train)})"
        )

    lines.append("")
    lines.append(
        "Edge is 'validated for now' only if most folds AND the held-out slice stay "
        "positive; LOW/empty folds mean too few trades to trust — widen the universe or "
        "reduce --walk-forward."
    )
    return "\n".join(lines)
