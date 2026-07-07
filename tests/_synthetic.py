"""Synthetic OHLCV builders for deterministic pattern tests."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ddbot.config import DetectionConfig

# Detection config tuned to the compact 18-bar fixtures below.
TEST_CFG = DetectionConfig(swing_k=2, min_bars_between=3)

# A clean "W": decline into B1 (idx 5, low 100), rally to a peak (idx 10, high 111),
# pull back to B2 (idx 15, low 100.5), then breakout bars.
W_LOWS = [110, 108, 106, 104, 102, 100, 102, 104, 106, 108,
          110, 108, 106, 104, 102, 100.5, 103, 101]


def make_ohlcv(lows, highs=None, closes=None, opens=None) -> pd.DataFrame:
    lows = np.asarray(lows, dtype=float)
    n = len(lows)
    highs = np.asarray(highs, dtype=float) if highs is not None else lows + 1.0
    # Default: close == open == low, i.e. no bar is "green" unless overridden. This
    # keeps confirmation from firing accidentally in structure-only fixtures.
    closes = np.asarray(closes, dtype=float) if closes is not None else lows.copy()
    opens = np.asarray(opens, dtype=float) if opens is not None else lows.copy()
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": 1_000.0},
        index=idx,
    )


def confirmed_w() -> pd.DataFrame:
    """W with a bullish breakout candle at idx 17 (close 113 > neckline 111, green)."""
    df = make_ohlcv(W_LOWS)
    df.iloc[17, df.columns.get_loc("open")] = 109.0
    df.iloc[17, df.columns.get_loc("close")] = 113.0
    df.iloc[17, df.columns.get_loc("high")] = 113.5
    return df
