"""Double-bottom (flush-reclaim / bear-trap) detection and reclaim confirmation.

Pattern (enter BELOW the neckline, on a failed breakdown):

    B1 (first bottom)  ->  recovery to interim peak (neckline)  ->  steep, high-volume
    flush that UNDERCUTS B1's low (B2)  ->  a CLEAN bullish candle reclaims back above B1's
    low (but still BELOW the neckline) within `reclaim_window` bars  =  ENTRY.

The reclaim bar must be one of two clean bullish shapes, both with a small upper wick (no
"long head"): a full green body (marubozu-like), or a bullish pin bar / hammer (small body
up top, long lower wick). See ``_is_valid_reclaim_bar``.

Stop = the B2 flush low (`DoubleBottom.stop_reference`, which is min(b1_low, b2_low) = b2_low
after the undercut). Target = the neckline.

Two entry points, both on closed bars only:
* ``detect``            — find the steep-undercut structures and return them as DETECTED.
* ``check_confirmation``— given a pending structure, CONFIRM on the reclaim, INVALIDATE if
                          price closes below the flush low or the reclaim window elapses.
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
    """Require price to have declined into the first bottom (a reversal needs something to reverse)."""
    start = max(0, b1 - cfg.max_bars_between)
    if start >= b1:
        return False
    prior_high = float(highs[start:b1].max())
    return prior_high >= base * (1 + cfg.min_prominence_pct)


def _atr(highs, lows, closes, end_idx: int, window: int) -> float | None:
    """Average True Range over the `window` bars ending at end_idx (needs a prior close)."""
    start = end_idx - window + 1
    if start < 1:
        return None  # not enough history for a true range
    trs = []
    for i in range(start, end_idx + 1):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    if not trs:
        return None
    return float(sum(trs) / len(trs))


def _flush_volume_ok(volumes, i: int, cfg: DetectionConfig) -> bool:
    """True if the flush bar carries a volume spike (capitulation). Safe fallbacks -> True."""
    if volumes is None:
        return True
    start = max(0, i - cfg.flush_volume_window)
    prior = volumes[start:i]
    if prior.size == 0:
        return True
    avg = float(np.nanmean(prior))
    if not np.isfinite(avg) or avg <= 0:
        return True
    v = volumes[i]
    if not np.isfinite(v):
        return True
    return v >= cfg.flush_volume_factor * avg


def _quality(p: DoubleBottom) -> tuple[float, float]:
    """Score a candidate: deeper flush first, then a lower B2 (more capitulation). Higher = better."""
    base = min(p.b1_low, p.b2_low)
    prominence = (p.neckline - base) / base if base else 0.0
    undercut = (p.b1_low - p.b2_low) / p.b1_low if p.b1_low else 0.0
    return (round(prominence, 6), round(undercut, 6))


def dedupe_by_neckline(
    patterns: list[DoubleBottom], neckline_tol_pct: float = 0.02
) -> list[DoubleBottom]:
    """Collapse candidates whose necklines sit at ~the same price to the strongest one."""
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
    """Return steep-undercut (flush) structures pending a reclaim, within the lookback window."""
    if df.empty:
        return []

    df = df.tail(cfg.lookback_bars)
    lows = df["low"].to_numpy(dtype=float)
    highs = df["high"].to_numpy(dtype=float)
    closes = df["close"].to_numpy(dtype=float)
    volumes = df["volume"].to_numpy(dtype=float) if "volume" in df.columns else None
    dates = _dates(df)
    n = len(df)

    patterns: list[DoubleBottom] = []
    for b1 in swing_lows(lows, cfg.swing_k):
        b1_low = lows[b1]

        if cfg.require_prior_downtrend and not _prior_downtrend(highs, b1, b1_low, cfg):
            continue

        # Interim peak (neckline): highest high in the recovery window after B1.
        hi_end = min(n, b1 + cfg.max_bars_between + 1)
        if hi_end <= b1 + 1:
            continue
        peak_idx = b1 + 1 + int(np.argmax(highs[b1 + 1 : hi_end]))
        peak = float(highs[peak_idx])
        if (peak - b1_low) / b1_low < cfg.min_prominence_pct:
            continue  # no real recovery / not enough room

        # Steep flush after the peak: lowest low within flush_max_bars.
        flush_end = min(n, peak_idx + cfg.flush_max_bars + 1)
        if flush_end <= peak_idx + 1:
            continue
        b2 = peak_idx + 1 + int(np.argmin(lows[peak_idx + 1 : flush_end]))
        b2_low = float(lows[b2])

        if cfg.require_undercut and not (b2_low < b1_low):
            continue  # must breach below the first bottom (bear-trap)

        atr = _atr(highs, lows, closes, peak_idx, cfg.flush_atr_window)
        if atr is None or atr <= 0:
            continue
        if (peak - b2_low) < cfg.flush_atr_mult * atr:
            continue  # not steep enough

        if not _flush_volume_ok(volumes, b2, cfg):
            continue  # no capitulation volume on the flush

        patterns.append(
            DoubleBottom(
                ticker=ticker,
                timeframe=timeframe,
                b1_date=dates[b1],
                b1_low=float(b1_low),
                b2_date=dates[b2],
                b2_low=b2_low,
                peak_date=dates[peak_idx],
                neckline=peak,
                state=PatternState.DETECTED,
            )
        )

    return dedupe_by_neckline(patterns)


def _is_valid_reclaim_bar(o: float, h: float, l: float, c: float, cfg: DetectionConfig) -> bool:
    """A clean bullish reclaim candle: small upper wick (no "long head") plus either a full
    green body or a bullish pin bar / hammer (long lower wick). Fractions are of the range."""
    if c <= o:                       # must be a green body
        return False
    rng = h - l
    if rng <= 0:
        return False
    upper_wick = h - c               # for a green bar the body top is the close
    lower_wick = o - l               # ...and the body bottom is the open
    if upper_wick > cfg.reclaim_max_upper_wick_frac * rng:
        return False                 # long upper wick -> reject (the FOXA-chart case)
    body = c - o
    if body >= cfg.reclaim_min_body_frac * rng:
        return True                  # full green bar
    if lower_wick >= cfg.reclaim_min_lower_wick_frac * rng:
        return True                  # bullish pin bar / hammer
    return False                     # weak/indecision bar


def swing_low_stop(flush_low: float, tick: float) -> float:
    """One tick below the immediate swing low before entry.

    In a flush-reclaim the most recent swing low ahead of the reclaim is the flush (B2)
    bar itself — the "latest big red bar" a chart reader points to. (A symmetric fractal
    can't even confirm it as a swing until `swing_k` bars later, i.e. after entry, so the
    flush low is both the correct and the only look-ahead-free choice.) The stop sits one
    tick under it, matching how a trader marks "just below the swing low".
    """
    return float(flush_low) - tick


def compute_stop(
    entry: float, flush_low: float, reclaim_bar_low: float,
    highs, lows, closes, confirm_idx: int, cfg: DetectionConfig,
) -> float:
    """The trade's stop, per cfg.stop_mode. Default 'atr' = entry - mult x ATR (a volatility-
    scaled stop that a backtest exit study found holds out-of-sample); 'reclaim_bar_low' is
    tight (below the entry bar); 'swing_low' is one tick below the most recent swing low;
    'flush_low' is the original deep-flush stop and the fallback."""
    if cfg.stop_mode == "reclaim_bar_low":
        return reclaim_bar_low
    if cfg.stop_mode == "swing_low":
        return swing_low_stop(flush_low, cfg.stop_tick)
    if cfg.stop_mode == "atr":
        atr = _atr(highs, lows, closes, confirm_idx, cfg.stop_atr_window)
        if atr is not None and atr > 0:
            return entry - cfg.stop_atr_mult * atr
    return flush_low


def compute_target(entry: float, neckline: float, stop: float, cfg: DetectionConfig) -> float:
    """The trade's target, per cfg.target_mode: an R-multiple of the risk, a measured move
    off the neckline, or the neckline itself."""
    if cfg.target_mode == "r_multiple":
        return entry + cfg.target_r_multiple * (entry - stop)
    if cfg.target_mode == "measured_move":
        return neckline + (neckline - stop)
    return neckline


def exit_options(p: DoubleBottom, df: pd.DataFrame, cfg: DetectionConfig) -> list[tuple[str, float, float]]:
    """Both stop methods the user trades, each with an R-multiple target, for the alert.

    Returns [(label, stop, target), ...] so a human can pick per trade:
      - swing-low: one tick below the flush (B2) swing low,
      - 1×ATR:     entry - 1×ATR(cfg.stop_atr_window).
    Both targets use cfg.target_r_multiple. The 1×ATR option is omitted if ATR is unknown.
    """
    if p.confirm_close is None:
        return []
    entry = float(p.confirm_close)
    flush_low = min(p.b1_low, p.b2_low)
    r = cfg.target_r_multiple

    opts: list[tuple[str, float, float]] = []
    s_swing = swing_low_stop(flush_low, cfg.stop_tick)
    opts.append(("Swing-low stop", s_swing, entry + r * (entry - s_swing)))

    dates = _dates(df)
    if p.confirm_date in dates:
        i = dates.index(p.confirm_date)
        atr = _atr(
            df["high"].to_numpy(dtype=float),
            df["low"].to_numpy(dtype=float),
            df["close"].to_numpy(dtype=float),
            i, cfg.stop_atr_window,
        )
        if atr is not None and atr > 0:
            s_atr = entry - atr  # 1×ATR (the user's "one ATR below entry")
            opts.append(("1×ATR stop", s_atr, entry + r * (entry - s_atr)))
    return opts


def check_confirmation(
    pattern: DoubleBottom, df: pd.DataFrame, cfg: DetectionConfig
) -> DoubleBottom:
    """Confirm on a below-neckline reclaim above B1's low; invalidate on a deeper flush, a
    reclaim that overshoots the neckline (a straight breakout), or an elapsed window.

    The reclaim bar must be a clean bullish candle (see ``_is_valid_reclaim_bar``)."""
    if df.empty:
        return pattern

    dates = _dates(df)
    if pattern.b2_date not in dates:
        return pattern  # window scrolled past the pattern; leave pending

    j = dates.index(pattern.b2_date)  # the flush-low bar
    opens = df["open"].to_numpy(dtype=float)
    highs = df["high"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float)
    closes = df["close"].to_numpy(dtype=float)
    b1_low = pattern.b1_low
    flush_low = pattern.stop_reference  # = b2 flush low
    neckline = pattern.neckline
    reclaim_end = min(len(df) - 1, j + cfg.reclaim_window)

    for i in range(j + 1, reclaim_end + 1):
        if closes[i] < flush_low:
            return pattern.with_state(PatternState.INVALIDATED)  # deeper flush -> reclaim failed
        if closes[i] > b1_low and _is_valid_reclaim_bar(
            opens[i], highs[i], lows[i], closes[i], cfg
        ):
            # A reclaim that overshoots the neckline is a straight breakout, not the
            # below-neckline bear-trap entry we want (target=neckline would be behind entry).
            if closes[i] >= neckline:
                return pattern.with_state(PatternState.INVALIDATED)
            entry = float(closes[i])
            stop_px = compute_stop(entry, flush_low, float(lows[i]), highs, lows, closes, i, cfg)
            return pattern.with_state(
                PatternState.CONFIRMED,
                confirm_date=dates[i],
                confirm_close=entry,
                stop_price=stop_px,
                target_price=compute_target(entry, neckline, stop_px, cfg),
            )

    # No reclaim: if the window has fully elapsed, the setup is dead.
    if (len(df) - 1) - j >= cfg.reclaim_window:
        return pattern.with_state(PatternState.INVALIDATED)
    return pattern
