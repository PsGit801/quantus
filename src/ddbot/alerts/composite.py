"""Fan-out alerter: send to every configured channel, isolating per-channel failures."""

from __future__ import annotations

import logging

from .base import Alerter

log = logging.getLogger(__name__)


class CompositeAlerter(Alerter):
    def __init__(self, channels: list[Alerter]):
        self.channels = channels

    def send(self, message: str, image_path: str | None = None) -> None:
        if not self.channels:
            log.warning("no alert channels configured; message dropped")
            return
        for channel in self.channels:
            name = type(channel).__name__
            try:
                channel.send(message, image_path)
                log.info("alert sent via %s", name)
            except Exception as exc:  # one channel failing must not block the others
                log.error("alert via %s failed: %s", name, exc)
