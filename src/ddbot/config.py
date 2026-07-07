"""Typed configuration loaded from YAML (watchlist + thresholds) and env (secrets)."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class DetectionConfig(BaseModel):
    """Tunable double-bottom detection thresholds."""

    lookback_bars: int = 90
    swing_k: int = 3
    bottom_tol_pct: float = 0.03
    min_prominence_pct: float = 0.05
    min_bars_between: int = 5
    max_bars_between: int = 50
    neckline_buffer_pct: float = 0.001
    require_prior_downtrend: bool = True
    # Volume confirmation: breakout candle volume must be >= volume_factor x the average
    # of the prior volume_avg_window bars. Filters weak, low-conviction breakouts.
    require_volume_confirmation: bool = True
    volume_avg_window: int = 20
    volume_factor: float = 1.0


class RiskConfig(BaseModel):
    """Position-sizing assumptions used for alert suggestions and the $ backtest."""

    account_equity: float = 10000.0
    risk_per_trade_pct: float = 0.01   # risk 1% of equity per trade
    max_position_pct: float = 0.25     # cap any single position at 25% of equity


class AppConfig(BaseModel):
    tickers: list[str]
    timeframes: list[str] = Field(default_factory=lambda: ["1d", "1wk"])
    drop_forming_bar: bool = True
    db_path: str = "ddbot.sqlite3"
    chart_dir: str = "charts"
    detection: DetectionConfig = Field(default_factory=DetectionConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)


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
