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

    @property
    def pattern_id(self) -> str:
        """Stable id keyed on the two bottoms — the dedup/idempotency anchor."""
        raw = f"{self.ticker}|{self.timeframe}|{self.b1_date.isoformat()}|{self.b2_date.isoformat()}"
        return hashlib.sha1(raw.encode()).hexdigest()[:16]

    @property
    def stop_reference(self) -> float:
        """Suggested invalidation / stop level: below the lower of the two bottoms."""
        return min(self.b1_low, self.b2_low)

    def with_state(self, state: PatternState, **kwargs) -> "DoubleBottom":
        return replace(self, state=state, **kwargs)
