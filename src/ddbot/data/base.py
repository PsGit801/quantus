"""DataProvider interface — the seam that lets us swap yfinance for Alpaca/Polygon later."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

# Canonical OHLCV frame contract every provider must return:
#   - tz-naive DatetimeIndex, ascending
#   - lowercase columns: open, high, low, close, volume
#   - only CLOSED bars (the forming bar is dropped by the provider)
OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]


class DataProvider(ABC):
    @abstractmethod
    def get_ohlcv(self, ticker: str, timeframe: str, lookback_bars: int) -> pd.DataFrame:
        """Return the canonical OHLCV frame, or an empty frame on failure."""
        raise NotImplementedError
