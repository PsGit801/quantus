"""Typed configuration loaded from YAML (watchlist + thresholds) and env (secrets)."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class DetectionConfig(BaseModel):
    """Tunable double-bottom (flush-reclaim / bear-trap) detection thresholds.

    Pattern: B1 (first bottom) -> recovery to interim peak (neckline) -> steep, high-volume
    flush that UNDERCUTS B1's low (B2) -> bullish candle reclaims above B1's low within
    reclaim_window bars = entry (below the neckline). Stop = B2 flush low; target = neckline.
    """

    lookback_bars: int = 90
    swing_k: int = 3
    min_prominence_pct: float = 0.05   # recovery: interim peak >= (1+this) x B1 low
    max_bars_between: int = 50         # max bars from B1 to the flush low
    require_prior_downtrend: bool = True

    # Steep flush into B2 (the capitulation leg)
    require_undercut: bool = True      # B2 low must be < B1 low (bear-trap)
    flush_atr_window: int = 14         # ATR window for the steepness measure
    flush_atr_mult: float = 3.0        # peak->B2 drop must be >= this x ATR
    flush_max_bars: int = 3            # peak->B2 must happen within this many bars
    flush_volume_factor: float = 1.5   # flush bar volume >= this x its average
    flush_volume_window: int = 20

    # Reclaim (entry trigger)
    reclaim_window: int = 6            # bullish close > B1 low within N bars of B2 (widened
                                       # from 4: lifts trades to n>=30 while holding the OOS edge)
    # The reclaim bar must be a CLEAN bullish candle (small upper wick = no "long head"):
    # either a full green body OR a bullish pin bar / hammer. Fractions are of the bar range (H-L).
    reclaim_min_body_frac: float = 0.60       # full green bar: body >= this x range
    reclaim_max_upper_wick_frac: float = 0.15  # both shapes: upper wick <= this x range
    reclaim_min_lower_wick_frac: float = 0.50  # hammer: lower wick >= this x range

    # Exit model (computed at confirmation, entry = reclaim close). Canonical is Method 1:
    # one tick below the flush (B2) swing low, with a 1.85R target. A walk-forward +
    # significance study found this (and a 1xATR variant) beat the earlier 3.5xATR /
    # measured-move exit out-of-sample. Defaults match config/config.yaml so behavior is the
    # same when the YAML is absent.
    stop_mode: str = "swing_low"       # "swing_low" | "atr" | "flush_low" | "reclaim_bar_low"
    stop_atr_window: int = 14
    stop_atr_mult: float = 3.5         # stop = entry - this x ATR when stop_mode == "atr"
    stop_tick: float = 0.01            # "swing_low": stop = flush swing low - this (one tick)
    target_mode: str = "r_multiple"    # "r_multiple" (entry + R x risk) | "measured_move" | "neckline"
    target_r_multiple: float = 1.85    # "r_multiple": target = entry + this x (entry - stop)


class RiskConfig(BaseModel):
    """Position-sizing assumptions used for alert suggestions and the $ backtest."""

    account_equity: float = 10000.0
    risk_per_trade_pct: float = 0.01   # risk 1% of equity per trade
    max_position_pct: float = 0.25     # cap any single position at 25% of equity


class MTFConfig(BaseModel):
    """Multi-timeframe confirmation: gate lower-timeframe alerts by a higher-timeframe trend."""

    require: bool = True
    higher_timeframe: str = "1wk"
    sma_window: int = 30          # higher-TF uptrend = close > SMA(sma_window)


class AppConfig(BaseModel):
    tickers: list[str]
    timeframes: list[str] = Field(default_factory=lambda: ["1d", "1wk"])
    drop_forming_bar: bool = True
    db_path: str = "ddbot.sqlite3"
    chart_dir: str = "charts"
    detection: DetectionConfig = Field(default_factory=DetectionConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    mtf: MTFConfig = Field(default_factory=MTFConfig)


class Secrets(BaseModel):
    """Alert-channel credentials, read from the environment."""

    telegram_token: str | None = None
    telegram_chat_id: str | None = None
    discord_webhook_url: str | None = None

    @classmethod
    def from_env(cls) -> "Secrets":
        return cls(
            telegram_token=os.getenv("TELEGRAM_TOKEN") or None,
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID") or None,
            discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL") or None,
        )


def load_config(path: str | Path) -> AppConfig:
    data = yaml.safe_load(Path(path).read_text()) or {}
    return AppConfig(**data)
