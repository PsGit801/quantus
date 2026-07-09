import os

import pandas as pd
from _synthetic import TEST_CFG, confirmed_w

from ddbot.alerts.base import Alerter
from ddbot.config import AppConfig, MTFConfig
from ddbot.engine import Engine
from ddbot.state.store import PatternStore


class FakeProvider:
    def __init__(self, df):
        self.df = df

    def get_ohlcv(self, ticker, timeframe, lookback_bars):
        return self.df


class TFProvider:
    """Returns different frames per timeframe (to exercise the MTF gate)."""

    def __init__(self, daily, weekly):
        self.daily = daily
        self.weekly = weekly

    def get_ohlcv(self, ticker, timeframe, lookback_bars):
        return self.weekly if timeframe == "1wk" else self.daily


def _downtrend_weekly(n=40):
    # n weekly bars ending well before the daily fixture's confirm date, declining.
    closes = [100.0 - i for i in range(n)]
    idx = pd.date_range("2023-01-01", periods=n, freq="7D")
    return pd.DataFrame({"open": closes, "high": closes, "low": closes,
                         "close": closes, "volume": [1000] * n}, index=idx)


class CountingAlerter(Alerter):
    def __init__(self):
        self.messages = []
        self.images = []

    def send(self, message, image_path=None):
        self.messages.append(message)
        self.images.append(image_path)


def _engine(tmp_path, alerter):
    cfg = AppConfig(
        tickers=["TEST"],
        timeframes=["1d"],
        db_path=str(tmp_path / "s.sqlite3"),
        chart_dir=str(tmp_path / "charts"),
        detection=TEST_CFG,
        mtf=MTFConfig(require=False),  # isolate detection/alert flow from the MTF gate
    )
    store = PatternStore(cfg.db_path)
    provider = FakeProvider(confirmed_w())
    return Engine(cfg, provider, store, alerter), store


def test_confirmation_fires_one_alert_and_is_idempotent(tmp_path):
    alerter = CountingAlerter()
    engine, store = _engine(tmp_path, alerter)

    # First run: detect -> confirm -> render chart -> alert.
    assert engine.run() == 1
    assert len(alerter.messages) == 1
    assert "Double Bottom" in alerter.messages[0]
    assert "TEST" in alerter.messages[0]
    # A chart image was rendered and passed to the alerter.
    assert alerter.images[0] and os.path.getsize(alerter.images[0]) > 0

    # Second run over identical data must not re-alert (hermes-safe).
    assert engine.run() == 0
    assert len(alerter.messages) == 1

    store.close()


def test_engine_scans_db_watchlist_over_config(tmp_path):
    # When the DB watchlist is non-empty, config tickers are NOT used (seed is skipped).
    alerter = CountingAlerter()
    engine, store = _engine(tmp_path, alerter)
    store.add_ticker("EXTRA")  # DB now non-empty -> run() skips seeding "TEST"

    assert engine.run() == 1
    assert "EXTRA" in alerter.messages[0]
    assert all("TEST" not in m for m in alerter.messages)

    store.close()


def test_mtf_suppresses_daily_alert_when_weekly_downtrend(tmp_path):
    # Daily pattern confirms, but the weekly timeframe is in a downtrend -> no alert.
    cfg = AppConfig(
        tickers=["TEST"], timeframes=["1d"],
        db_path=str(tmp_path / "s.sqlite3"), chart_dir=str(tmp_path / "charts"),
        detection=TEST_CFG, mtf=MTFConfig(require=True, higher_timeframe="1wk", sma_window=30),
    )
    store = PatternStore(cfg.db_path)
    alerter = CountingAlerter()
    provider = TFProvider(daily=confirmed_w(), weekly=_downtrend_weekly())
    engine = Engine(cfg, provider, store, alerter)

    assert engine.run() == 0            # suppressed by the weekly downtrend
    assert alerter.messages == []
    store.close()
