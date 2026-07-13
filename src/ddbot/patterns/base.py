"""Pattern data model shared across detectors and the state store."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import date
from enum import Enum


class PatternState(str, Enum):
    DETECTED = "DETECTED"        # W structure found, awaiting breakout confirmation
    CONFIRMED = "CONFIRMED"      # bullish candle closed above the neckline -> alert
    INVALIDATED = "INVALIDATED"  # broke below the bottoms, or expired unconfirmed


@dataclass(frozen=True)
class DoubleBottom:
    ticker: str
    timeframe: str
    b1_date: date
    b1_low: float
    b2_date: date
    b2_low: float
    peak_date: date
    neckline: float
    state: PatternState = PatternState.DETECTED
    confirm_date: date | None = None
    confirm_close: float | None = None
    # Exit levels computed at confirmation (strategy-configured; see check_confirmation).
    # None until confirmed, then fall back to the flush low / neckline respectively.
    stop_price: float | None = None
    target_price: float | None = None

    @property
    def pattern_id(self) -> str:
        """Stable id keyed on the two bottoms — the dedup/idempotency anchor."""
        raw = f"{self.ticker}|{self.timeframe}|{self.b1_date.isoformat()}|{self.b2_date.isoformat()}"
        return hashlib.sha1(raw.encode()).hexdigest()[:16]

    @property
    def stop_reference(self) -> float:
        """The trade's stop: the configured stop computed at confirmation if present,
        else the fallback below the lower of the two bottoms (the flush low)."""
        if self.stop_price is not None:
            return self.stop_price
        return min(self.b1_low, self.b2_low)

    @property
    def target(self) -> float:
        """The trade's target: the configured target computed at confirmation if present,
        else the neckline (first resistance for a below-neckline reclaim entry)."""
        return self.target_price if self.target_price is not None else self.neckline

    def with_state(self, state: PatternState, **kwargs) -> "DoubleBottom":
        return replace(self, state=state, **kwargs)
