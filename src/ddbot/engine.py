"""Orchestration: fetch -> detect -> persist -> confirm -> alert, per ticker."""

from __future__ import annotations

import logging

from .alerts.base import Alerter
from .alerts.formatter import format_signal
from .charts.chart import render
from .config import AppConfig
from .data.base import DataProvider
from .patterns.base import PatternState
from .patterns.double_bottom import check_confirmation, detect
from .state.store import PatternStore

log = logging.getLogger(__name__)


class Engine:
    def __init__(
        self,
        cfg: AppConfig,
        provider: DataProvider,
        store: PatternStore,
        alerter: Alerter | None,
        dry_run: bool = False,
    ):
        self.cfg = cfg
        self.provider = provider
        self.store = store
        self.alerter = alerter
        self.dry_run = dry_run

    def run(self) -> int:
        """Process every ticker on every configured timeframe. Returns alerts fired."""
        # Watchlist lives in the DB (editable from Telegram); config tickers seed it.
        self.store.seed_watchlist(self.cfg.tickers)
        tickers = self.store.list_tickers()

        alerts = 0
        for ticker in tickers:
            for timeframe in self.cfg.timeframes:
                try:
                    alerts += self._process(ticker, timeframe)
                except Exception as exc:  # isolate per-(ticker, timeframe) failures
                    log.exception("error processing %s %s: %s", ticker, timeframe, exc)
        return alerts

    def _process(self, ticker: str, timeframe: str) -> int:
        df = self.provider.get_ohlcv(ticker, timeframe, self.cfg.detection.lookback_bars)
        if df.empty:
            log.info("%s %s: no data, skipping", ticker, timeframe)
            return 0

        # 1. Record any newly-found structures as pending (existing ones are left untouched).
        for pattern in detect(df, ticker, timeframe, self.cfg.detection):
            if self.store.upsert_detected(pattern):
                log.info("%s %s: new double-bottom detected (%s)", ticker, timeframe, pattern.pattern_id)

        # 2. Re-evaluate every pending pattern for confirmation / invalidation.
        alerts = 0
        for pattern in self.store.pending_patterns(ticker, timeframe):
            updated = check_confirmation(pattern, df, self.cfg.detection)
            if updated.state is not pattern.state:
                self.store.update_state(updated)
                log.info("%s %s: %s -> %s", ticker, timeframe, pattern.pattern_id, updated.state.value)

            if updated.state is PatternState.CONFIRMED and not self.store.is_alerted(
                updated.pattern_id
            ):
                self._alert(updated, df)
                self.store.mark_alerted(updated.pattern_id)
                alerts += 1
        return alerts

    def _alert(self, pattern, df) -> None:
        message = format_signal(pattern, self.cfg.risk)
        try:
            chart_path = render(df, pattern, self.cfg.chart_dir)
        except Exception as exc:  # never let a chart failure block the alert
            log.error("chart render failed for %s: %s", pattern.pattern_id, exc)
            chart_path = None

        if self.dry_run or self.alerter is None:
            print(message)
            if chart_path:
                print(f"[chart] {chart_path}")
            print("-" * 40)
        else:
            self.alerter.send(message, chart_path)
