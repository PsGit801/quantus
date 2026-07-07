"""Multi-timeframe confirmation — higher-timeframe trend filter.

A daily double-bottom is higher-conviction when the weekly trend agrees. `is_uptrend`
answers "as of this date, is the higher timeframe in an uptrend?" using a simple
close-above-SMA rule. Safe fallback: if there isn't enough higher-TF history, it
returns True (don't block) rather than silently suppressing signals.
"""

from __future__ import annotations

from datetime import date

import pandas as pd


def is_uptrend(df: pd.DataFrame, as_of: date, sma_window: int) -> bool:
    """True if the last higher-TF close on/before `as_of` is above its SMA(sma_window)."""
    if df is None or df.empty:
        return True

    dates = [ts.date() if hasattr(ts, "date") else ts for ts in df.index]
    # bars on or before the confirmation date (no look-ahead)
    upto = [i for i, d in enumerate(dates) if d <= as_of]
    if len(upto) < sma_window:
        return True  # not enough history to judge -> don't block

    closes = df["close"].to_numpy(dtype=float)
    window = closes[upto[-sma_window:]]
    sma = float(window.mean())
    last_close = float(closes[upto[-1]])
    return last_close > sma
