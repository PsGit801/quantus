import os

from _synthetic import TEST_CFG, confirmed_w

from ddbot.alerts.base import Alerter
from ddbot.config import AppConfig
from ddbot.engine import Engine
from ddbot.state.store import PatternStore


class FakeProvider:
    def __init__(self, df):
        self.df = df

    def get_ohlcv(self, ticker, timeframe, lookback_bars):
        return self.df


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
    assert "Double Bottom confirmed" in alerter.messages[0]
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

    store.close()
