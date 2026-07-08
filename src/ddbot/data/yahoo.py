"""yfinance-backed daily OHLCV provider."""

from __future__ import annotations

import logging
import re

import pandas as pd

from .base import OHLCV_COLUMNS, DataProvider

log = logging.getLogger(__name__)

# Valid ticker shape: 1–10 chars from [A-Z0-9.-], with at least one alphanumeric
# (so pure punctuation like "..." or "---" is rejected).
_SYMBOL_RE = re.compile(r"^(?=.*[A-Z0-9])[A-Z0-9.\-]{1,10}$")


def normalize_symbol(raw: str) -> str | None:
    """Clean user-entered text into a candidate ticker, or None if it can't be one.

    Uppercases, strips a leading ``$`` and surrounding whitespace, and enforces a
    conservative charset so nothing unsafe reaches a yfinance call or the DB.
    """
    if raw is None:
        return None
    s = raw.strip().upper().lstrip("$").strip()
    return s if _SYMBOL_RE.match(s) else None


def validate_symbol(ticker: str) -> bool:
    """True if Yahoo returns recent data for the symbol (rejects typos/junk)."""
    import yfinance as yf

    try:
        df = yf.download(ticker, period="5d", interval="1d", progress=False, threads=False)
    except Exception as exc:
        log.warning("validate_symbol fetch failed for %s: %s", ticker, exc)
        return False
    return df is not None and not df.empty

# yfinance interval strings we support, and how many calendar days one bar spans
# (used to size the fetch window so we always clear >= lookback_bars trading bars).
_INTERVAL = {"1d": "1d", "1wk": "1wk"}
_DAYS_PER_BAR = {"1d": 1.6, "1wk": 7.2}


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten yfinance output to the canonical lowercase OHLCV contract."""
    # Recent yfinance returns MultiIndex columns even for a single ticker.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)
    keep = [c for c in OHLCV_COLUMNS if c in df.columns]
    df = df[keep].copy()
    # Drop tz info so downstream date handling is uniform.
    if isinstance(df.index, pd.DatetimeIndex) and df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df = df.dropna(subset=["open", "high", "low", "close"])
    return df.sort_index()


class YahooDataProvider(DataProvider):
    def __init__(self, drop_forming_bar: bool = True):
        self.drop_forming_bar = drop_forming_bar

    def get_ohlcv(self, ticker: str, timeframe: str = "1d", lookback_bars: int = 90) -> pd.DataFrame:
        interval = _INTERVAL.get(timeframe)
        if interval is None:
            raise ValueError(f"Unsupported timeframe {timeframe!r}; supported: {list(_INTERVAL)}")

        # Ask for calendar days generously so we clear weekends/holidays and still
        # have >= lookback_bars bars (plus room for the prior-downtrend lookback).
        period_days = int(lookback_bars * _DAYS_PER_BAR[timeframe] * 1.3) + 40

        import time

        import yfinance as yf  # imported lazily so pattern tests don't need the dep

        # Retry with backoff — a transient network/DNS blip shouldn't skip the ticker.
        raw = None
        attempts = 3
        for attempt in range(attempts):
            try:
                raw = yf.download(
                    ticker,
                    period=f"{period_days}d",
                    interval=interval,
                    auto_adjust=True,  # split/dividend-adjusted
                    progress=False,
                    threads=False,
                )
                if raw is not None and not raw.empty:
                    break
            except Exception as exc:  # network / symbol / library errors — never crash the run
                log.warning("fetch failed for %s (attempt %d/%d): %s", ticker, attempt + 1, attempts, exc)
            if attempt < attempts - 1:
                time.sleep(2 * (attempt + 1))  # 2s, then 4s

        if raw is None or raw.empty:
            log.warning("no data returned for %s after %d attempts", ticker, attempts)
            return pd.DataFrame(columns=OHLCV_COLUMNS)

        df = _normalize(raw)

        # Only ever act on closed bars — the current-day daily bar repaints intraday.
        if self.drop_forming_bar and len(df) > 0:
            df = df.iloc[:-1]

        return df.tail(lookback_bars)
