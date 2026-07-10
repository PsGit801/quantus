"""Render a confirmed double-bottom to a candlestick PNG.

The chart shows the two bottoms (marked), the neckline (dashed), and highlights the
bullish green breakout candle so the user can eyeball the setup from the alert alone.
"""

from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")  # headless: no display on hermes / CI

import matplotlib.pyplot as plt  # noqa: E402
import mplfinance as mpf  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from ..patterns.base import DoubleBottom  # noqa: E402

# mplfinance requires capitalized OHLCV column names.
_RENAME = {"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}

_PRE_PAD = 5   # bars shown before the first bottom
_POST_PAD = 2  # bars shown after the breakout


def _pos(dates: list, target) -> int | None:
    try:
        return dates.index(target)
    except ValueError:
        return None


def render(df: pd.DataFrame, pattern: DoubleBottom, out_dir: str) -> str:
    """Render the pattern's confirmation window to a PNG and return its path."""
    os.makedirs(out_dir, exist_ok=True)

    data = df.rename(columns=_RENAME)
    dates = [ts.date() if hasattr(ts, "date") else ts for ts in data.index]

    b1 = _pos(dates, pattern.b1_date)
    b2 = _pos(dates, pattern.b2_date)
    conf = _pos(dates, pattern.confirm_date) if pattern.confirm_date else None

    # Slice a readable window around the pattern (clamped to available data).
    anchor_lo = min(x for x in (b1, b2) if x is not None)
    anchor_hi = max(x for x in (b1, b2, conf) if x is not None)
    lo = max(0, anchor_lo - _PRE_PAD)
    hi = min(len(data) - 1, anchor_hi + _POST_PAD)
    window = data.iloc[lo : hi + 1]

    # Scatter markers, aligned to the sliced window (NaN = no marker on that bar).
    lows_marker = np.full(len(window), np.nan)
    close_marker = np.full(len(window), np.nan)
    for idx, low in ((b1, pattern.b1_low), (b2, pattern.b2_low)):
        if idx is not None and lo <= idx <= hi:
            lows_marker[idx - lo] = low * 0.995  # nudge below the bar for visibility
    if conf is not None and lo <= conf <= hi:
        close_marker[conf - lo] = pattern.confirm_close

    addplots = []
    if not np.all(np.isnan(lows_marker)):
        addplots.append(
            mpf.make_addplot(lows_marker, type="scatter", marker="^", markersize=140, color="tab:blue")
        )
    if not np.all(np.isnan(close_marker)):
        addplots.append(
            mpf.make_addplot(close_marker, type="scatter", marker="*", markersize=220, color="tab:green")
        )

    # NB: no full-height vline on the confirm bar — mplfinance draws it across the whole
    # price panel, where it overlaps the entry candle and reads like a huge wick. The green
    # star (close_marker) already marks the confirmed bar.

    out_path = os.path.join(out_dir, f"{pattern.ticker}_{pattern.timeframe}_{pattern.pattern_id}.png")
    fig, _ = mpf.plot(
        window,
        type="candle",
        style="yahoo",
        volume=True,
        hlines=dict(hlines=[pattern.neckline], colors=["orange"], linestyle="--", linewidths=1),
        addplot=addplots if addplots else None,
        title=f"{pattern.ticker} {pattern.timeframe} — Double Bottom confirmed",
        figsize=(11, 7),
        returnfig=True,
    )
    fig.savefig(out_path, dpi=100, bbox_inches="tight")
    plt.close(fig)
    return out_path
