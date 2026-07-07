"""Swing-point (fractal) detection.

A bar is a swing low if its low is the minimum over a symmetric window of ``k`` bars
on each side; symmetric definition for swing highs. Using +/-k *future* bars is safe
for this bot: we only ever alert on the later confirmation candle, so no look-ahead
edge is gained over what a live trader would see once the swing has formed.
"""

from __future__ import annotations

import numpy as np


def swing_lows(lows, k: int) -> list[int]:
    values = np.asarray(lows, dtype=float)
    n = len(values)
    out: list[int] = []
    for i in range(k, n - k):
        window = values[i - k : i + k + 1]
        # argmin returns the first minimum; requiring it to be the center makes the
        # center the (uniquely-first) lowest bar, avoiding plateau double-counting.
        if int(np.argmin(window)) == k:
            out.append(i)
    return out


def swing_highs(highs, k: int) -> list[int]:
    values = np.asarray(highs, dtype=float)
    n = len(values)
    out: list[int] = []
    for i in range(k, n - k):
        window = values[i - k : i + k + 1]
        if int(np.argmax(window)) == k:
            out.append(i)
    return out
