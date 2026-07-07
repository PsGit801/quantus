"""Position sizing — fixed-fractional risk model.

Turns a signal's entry and stop into a concrete share count: risk a fixed fraction of
account equity per trade, capped so a very tight stop can't blow up into an oversized
position. Pure and testable; used by alerts (suggested size) and by the $ backtest.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Sizing:
    shares: int
    dollar_risk: float       # shares * (entry - stop)
    position_value: float    # shares * entry
    notional_pct: float      # position_value / equity
    capped: bool             # True if the max-position cap reduced the size


def position_size(
    entry: float,
    stop: float,
    equity: float,
    risk_pct: float,
    max_position_pct: float = 1.0,
) -> Sizing:
    """Fixed-fractional size: risk `risk_pct` of `equity`, capped at `max_position_pct`."""
    risk_per_share = entry - stop
    if risk_per_share <= 0 or equity <= 0 or entry <= 0:
        return Sizing(0, 0.0, 0.0, 0.0, False)

    risk_shares = math.floor((equity * risk_pct) / risk_per_share)
    max_shares = math.floor((equity * max_position_pct) / entry)
    shares = min(risk_shares, max_shares)
    capped = shares < risk_shares
    shares = max(shares, 0)

    position_value = shares * entry
    return Sizing(
        shares=shares,
        dollar_risk=round(shares * risk_per_share, 2),
        position_value=round(position_value, 2),
        notional_pct=round(position_value / equity, 4) if equity else 0.0,
        capped=capped,
    )
