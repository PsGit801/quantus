"""Synthetic OHLCV builders for deterministic flush-reclaim pattern tests."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ddbot.config import DetectionConfig

# Config tuned to the compact 20-bar flush-reclaim fixture below.
TEST_CFG = DetectionConfig(
    swing_k=2,
    lookback_bars=18,
    min_prominence_pct=0.05,
    max_bars_between=50,
    require_prior_downtrend=True,
    require_undercut=True,
    flush_atr_window=5,
    flush_atr_mult=2.0,
    flush_max_bars=3,
    flush_volume_factor=1.5,
    flush_volume_window=5,
    reclaim_window=4,
    # Pin the clean-reclaim-bar thresholds so tests are decoupled from config-default drift.
    reclaim_min_body_frac=0.60,
    reclaim_max_upper_wick_frac=0.15,
    reclaim_min_lower_wick_frac=0.50,
    # Pin the exit model to the simple flush-low/neckline so fixture expectations are stable
    # (the live default is atr/measured_move; exercised in test_double_bottom directly).
    stop_mode="flush_low",
    target_mode="neckline",
)

# A flush-reclaim: decline into B1 (idx5, low 100), recover to a peak (idx12, high 114),
# a steep high-volume flush that undercuts B1 -> B2 (idx15, low 88), then a bullish reclaim
# candle (idx17, close 103 > B1 low 100). Entry = 103; neckline (target) = 114; stop = 88.
_OPEN = [114, 111, 108, 105, 102, 101, 103, 105, 107, 106, 108, 110, 111, 100, 92, 89, 95, 95, 101, 103]
_HIGH = [115, 112, 109, 106, 103, 102, 105, 107, 109, 108, 111, 112, 114, 106, 99, 91, 96, 104, 103, 105]
_LOW = [113, 110, 107, 104, 101, 100, 102, 104, 106, 105, 107, 109, 110, 104, 96, 88, 92, 95, 100, 102]
_CLOSE = [114, 111, 108, 105, 102, 101, 103, 105, 107, 106, 108, 110, 111, 100, 92, 89, 93, 103, 101, 103]
_VOL = [1000] * 20
_VOL[15] = 5000  # capitulation volume on the flush


def make_ohlcv(lows, highs=None, closes=None, opens=None, volumes=None) -> pd.DataFrame:
    lows = np.asarray(lows, dtype=float)
    n = len(lows)
    highs = np.asarray(highs, dtype=float) if highs is not None else lows + 1.0
    closes = np.asarray(closes, dtype=float) if closes is not None else lows.copy()
    opens = np.asarray(opens, dtype=float) if opens is not None else lows.copy()
    vol = np.asarray(volumes, dtype=float) if volumes is not None else np.full(n, 1000.0)
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": vol},
        index=idx,
    )


def flush_reclaim() -> pd.DataFrame:
    """The canonical flush-reclaim fixture (see indices above)."""
    return make_ohlcv(_LOW, _HIGH, _CLOSE, _OPEN, _VOL)


# Backwards-compatible alias for tests that import the old fixture name.
confirmed_w = flush_reclaim
