"""Alerter interface — swappable notification channels."""

from __future__ import annotations

from abc import ABC, abstractmethod


class Alerter(ABC):
    @abstractmethod
    def send(self, message: str, image_path: str | None = None) -> None:
        raise NotImplementedError
