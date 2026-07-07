"""Discord alerter via an incoming webhook."""

from __future__ import annotations

import logging

import requests

from .base import Alerter

log = logging.getLogger(__name__)


class DiscordAlerter(Alerter):
    def __init__(self, webhook_url: str, timeout: float = 10.0):
        self.webhook_url = webhook_url
        self.timeout = timeout

    def send(self, message: str, image_path: str | None = None) -> None:
        if image_path:
            import os

            with open(image_path, "rb") as f:
                resp = requests.post(
                    self.webhook_url,
                    data={"content": message},
                    files={"file": (os.path.basename(image_path), f, "image/png")},
                    timeout=self.timeout,
                )
        else:
            resp = requests.post(
                self.webhook_url,
                json={"content": message},
                timeout=self.timeout,
            )
        resp.raise_for_status()
