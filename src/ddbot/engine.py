"""Orchestration: fetch -> detect -> persist -> confirm -> alert, per ticker."""

from __future__ import annotations

import logging
from datetime import date

from .alerts.base import Alerter
from .alerts.formatter import format_signal
from .charts.chart import render
from .config import AppConfig
from .data.base import DataProvider
from .mtf import is_uptrend
from .patterns.base import PatternState
from .patterns.double_bottom import check_confirmation, detect, exit_options
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
        self._higher_df_cache: dict = {}

    def run(self) -> int:
        """Process every ticker on every configured timeframe. Returns alerts fired."""
        # Watchlist lives in the DB (editable from Telegram); config tickers seed it.
        self.store.seed_watchlist(self.cfg.tickers)
        tickers = self.store.list_tickers()
        self._higher_df_cache = {}

        alerts = 0
        for ticker in tickers:
            for timeframe in self.cfg.timeframes:
                try:
                    alerts += self._process(ticker, timeframe)
                except Exception as exc:  # isolate per-(ticker, timeframe) failures
                    log.exception("error processing %s %s: %s", ticker, timeframe, exc)
        # Heartbeat: record that a real scan completed (read by the weekly digest's health
        # check). Skipped in dry-run so a preview never looks like a live scan.
        if not self.dry_run:
            self.store.kv_set("last_scan_at", date.today().isoformat())
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
            # In a dry-run, don't persist the transition either: advancing to CONFIRMED here
            # would strand the pattern (pending_patterns skips it), so the real scan could
            # never confirm/alert it. The in-memory `updated` still drives the preview below.
            if updated.state is not pattern.state and not self.dry_run:
                self.store.update_state(updated)
                log.info("%s %s: %s -> %s", ticker, timeframe, pattern.pattern_id, updated.state.value)

            if updated.state is PatternState.CONFIRMED and not self.store.is_alerted(
                updated.pattern_id
            ):
                if self._mtf_ok(ticker, timeframe, updated.confirm_date):
                    self._alert(updated, df)
                    # A dry-run is a read-only preview: never consume the signal, or the
                    # real scheduled scan would skip an alert the user never actually received.
                    if not self.dry_run:
                        self.store.mark_alerted(updated.pattern_id)
                    alerts += 1
                else:
                    # Higher timeframe disagrees — suppress. State stays CONFIRMED so it
                    # won't be re-evaluated (not re-alerted) on later runs.
                    log.info("%s %s: %s suppressed (higher-TF not in uptrend)",
                             ticker, timeframe, updated.pattern_id)
        return alerts

    def _mtf_ok(self, ticker: str, timeframe: str, confirm_date) -> bool:
        """Gate lower-timeframe alerts by the higher-timeframe trend (if enabled)."""
        m = self.cfg.mtf
        if not m.require or timeframe == m.higher_timeframe:
            return True
        if ticker not in self._higher_df_cache:
            lookback = max(self.cfg.detection.lookback_bars, m.sma_window * 3)
            self._higher_df_cache[ticker] = self.provider.get_ohlcv(
                ticker, m.higher_timeframe, lookback
            )
        return is_uptrend(self._higher_df_cache[ticker], confirm_date, m.sma_window)

    def _alert(self, pattern, df) -> None:
        options = exit_options(pattern, df, self.cfg.detection)
        message = format_signal(pattern, self.cfg.risk, options)
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
