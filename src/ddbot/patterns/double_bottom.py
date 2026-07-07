"""Double-bottom detection and breakout confirmation.

Two entry points:

* ``detect``            — scan a fresh OHLCV frame for valid "W" structures and return
                          them as DETECTED (pending) patterns.
* ``check_confirmation``— given a stored pending pattern and a fresh frame, decide whether
                          it has CONFIRMED (bullish breakout close above neckline),
                          INVALIDATED (broke below the bottoms / expired), or is still
                          pending.

Both operate only on the closed bars supplied by the DataProvider.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from ..config import DetectionConfig
from .base import DoubleBottom, PatternState
from .swings import swing_lows


def _dates(df: pd.DataFrame) -> list[date]:
    return [ts.date() if hasattr(ts, "date") else ts for ts in df.index]


def _prior_downtrend(highs: np.ndarray, b1: int, base: float, cfg: DetectionConfig) -> bool:
    """Require price to have declined into the first bottom.

    A double bottom is a reversal pattern: without a preceding decline it's just a wiggle.
    We check that some bar in the run-up window before B1 traded meaningfully above it.
    """
    start = max(0, b1 - cfg.max_bars_between)
    if start >= b1:
        return False  # not enough history before B1 to establish a prior trend
    prior_high = float(highs[start:b1].max())
    return prior_high >= base * (1 + cfg.min_prominence_pct)


def _quality(p: DoubleBottom) -> tuple[float, float]:
    """Score a candidate: deeper W first, then more symmetric bottoms. Higher = better."""
    base = min(p.b1_low, p.b2_low)
    prominence = (p.neckline - base) / base
    similarity = abs(p.b1_low - p.b2_low) / base  # smaller is more symmetric
    return (round(prominence, 6), -round(similarity, 6))


def dedupe_by_neckline(
    patterns: list[DoubleBottom], neckline_tol_pct: float = 0.02
) -> list[DoubleBottom]:
    """Collapse candidates whose necklines sit at ~the same price to the strongest one.

    The pair-scan emits a DoubleBottom for every valid (B1, B2); many describe the *same*
    resistance breakout (same or adjacent peaks within a small price band) and would fire
    several near-identical alerts. Cluster necklines within ``neckline_tol_pct`` and keep the
    strongest (deepest, most symmetric) per cluster, so one breakout = one alert.
    """
    clusters: list[dict] = []
    for p in sorted(patterns, key=lambda x: x.neckline):
        score = _quality(p)
        placed = False
        for c in clusters:
            if abs(p.neckline - c["ref"]) / c["ref"] <= neckline_tol_pct:
                if score > c["score"]:
                    c["best"], c["score"] = p, score
                placed = True
                break
        if not placed:
            clusters.append({"ref": p.neckline, "best": p, "score": score})
    return sorted((c["best"] for c in clusters), key=lambda p: (p.b1_date, p.b2_date))


def detect(
    df: pd.DataFrame, ticker: str, timeframe: str, cfg: DetectionConfig
) -> list[DoubleBottom]:
    """Return all valid double-bottom structures within the lookback window."""
    if df.empty:
        return []

    df = df.tail(cfg.lookback_bars)
    lows = df["low"].to_numpy(dtype=float)
    highs = df["high"].to_numpy(dtype=float)
    dates = _dates(df)

    lows_idx = swing_lows(lows, cfg.swing_k)
    patterns: list[DoubleBottom] = []

    for a in range(len(lows_idx)):
        for b in range(a + 1, len(lows_idx)):
            b1, b2 = lows_idx[a], lows_idx[b]

            gap = b2 - b1
            if gap < cfg.min_bars_between or gap > cfg.max_bars_between:
                continue

            l1, l2 = lows[b1], lows[b2]
            if abs(l2 - l1) / l1 > cfg.bottom_tol_pct:
                continue

            between = highs[b1 + 1 : b2]
            if between.size == 0:
                continue
            peak_off = int(np.argmax(between))
            peak_idx = b1 + 1 + peak_off
            neckline = float(highs[peak_idx])

            base = min(l1, l2)
            if (neckline - base) / base < cfg.min_prominence_pct:
                continue

            if cfg.require_prior_downtrend and not _prior_downtrend(highs, b1, base, cfg):
                continue

            patterns.append(
                DoubleBottom(
                    ticker=ticker,
                    timeframe=timeframe,
                    b1_date=dates[b1],
                    b1_low=float(l1),
                    b2_date=dates[b2],
                    b2_low=float(l2),
                    peak_date=dates[peak_idx],
                    neckline=neckline,
                    state=PatternState.DETECTED,
                )
            )

    return dedupe_by_neckline(patterns)


def _volume_ok(volumes, i: int, cfg: DetectionConfig) -> bool:
    """True if bar i's volume >= volume_factor x the prior-window average.

    Safe fallbacks: if volume data is missing, or there's no prior history, or the
    average is zero/NaN, don't block confirmation.
    """
    if volumes is None:
        return True
    start = max(0, i - cfg.volume_avg_window)
    prior = volumes[start:i]
    if prior.size == 0:
        return True
    avg = float(np.nanmean(prior))
    if not np.isfinite(avg) or avg <= 0:
        return True
    vol_i = volumes[i]
    if not np.isfinite(vol_i):
        return True
    return vol_i >= cfg.volume_factor * avg


def check_confirmation(
    pattern: DoubleBottom, df: pd.DataFrame, cfg: DetectionConfig
) -> DoubleBottom:
    """Evaluate a pending pattern against fresh bars; return the (possibly) updated pattern."""
    if df.empty:
        return pattern

    dates = _dates(df)
    if pattern.b2_date not in dates:
        # Data window scrolled past the pattern; leave it pending for now.
        return pattern

    j = dates.index(pattern.b2_date)
    opens = df["open"].to_numpy(dtype=float)
    closes = df["close"].to_numpy(dtype=float)
    volumes = df["volume"].to_numpy(dtype=float) if "volume" in df.columns else None
    stop = pattern.stop_reference
    trigger = pattern.neckline * (1 + cfg.neckline_buffer_pct)

    for i in range(j + 1, len(df)):
        if closes[i] < stop:
            return pattern.with_state(PatternState.INVALIDATED)
        if closes[i] > trigger and closes[i] > opens[i]:
            # Require the breakout candle to carry volume; if it's weak, keep waiting
            # for a stronger breakout rather than confirming on low conviction.
            if cfg.require_volume_confirmation and not _volume_ok(volumes, i, cfg):
                continue
            return pattern.with_state(
                PatternState.CONFIRMED,
                confirm_date=dates[i],
                confirm_close=float(closes[i]),
            )

    # No breakout yet — expire if the pattern has gone stale.
    bars_since_b2 = (len(df) - 1) - j
    if bars_since_b2 > cfg.max_bars_between:
        return pattern.with_state(PatternState.INVALIDATED)

    return pattern
