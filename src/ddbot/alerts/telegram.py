"""Telegram alerter via the Bot API sendMessage endpoint."""

from __future__ import annotations

import logging

import requests

from .base import Alerter

log = logging.getLogger(__name__)


class TelegramAlerter(Alerter):
    def __init__(self, token: str, chat_id: str, timeout: float = 10.0):
        self.token = token
        self.chat_id = chat_id
        self.timeout = timeout

    def send(self, message: str, image_path: str | None = None) -> None:
        if image_path:
            url = f"https://api.telegram.org/bot{self.token}/sendPhoto"
            with open(image_path, "rb") as photo:
                resp = requests.post(
                    url,
                    data={"chat_id": self.chat_id, "caption": message, "parse_mode": "Markdown"},
                    files={"photo": photo},
                    timeout=self.timeout,
                )
        else:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            resp = requests.post(
                url,
                json={"chat_id": self.chat_id, "text": message, "parse_mode": "Markdown"},
                timeout=self.timeout,
            )
        resp.raise_for_status()
