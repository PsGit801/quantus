"""Parameter sweep: grid-search detection AND exit-model thresholds, rank by backtested edge.

For each combination of parameter values it re-runs the backtest, then splits the
trades into in-sample (older) and out-of-sample (newest `oos_split` fraction) by entry
date. Ranking on in-sample while showing out-of-sample side by side guards against
curve-fitting — a combo whose OOS edge collapses was overfit. Swept params may be either
DetectionConfig fields (e.g. flush_atr_mult) or BacktestConfig exit-model fields (stop,
target, atr_mult, ...); each row also flags whether its OOS edge is statistically
significant (bootstrap CI on mean R above zero).
"""

from __future__ import annotations

import dataclasses
import itertools
from dataclasses import dataclass
from datetime import date

import pandas as pd

from ..config import DetectionConfig
from .engine import BacktestConfig, Trade, backtest_ticker
from .metrics import Stats, significance, summarize

_BT_FIELDS = {f.name for f in dataclasses.fields(BacktestConfig)}


def parse_sweep_specs(specs: list[str]) -> dict[str, list[str]]:
    """['volume_factor=1.0,1.5', 'min_prominence_pct=0.05,0.08'] -> {param: [raw values]}."""
    out: dict[str, list[str]] = {}
    for spec in specs:
        if "=" not in spec:
            raise ValueError(f"bad --sweep {spec!r}; expected PARAM=v1,v2,...")
        param, _, raw = spec.partition("=")
        values = [v.strip() for v in raw.split(",") if v.strip()]
        if not values:
            raise ValueError(f"--sweep {param} has no values")
        out[param.strip()] = values
    return out


def cast_value(base: DetectionConfig, param: str, raw: str, bt: BacktestConfig | None = None):
    """Cast a raw sweep value to the type of the matching field.

    Looks in DetectionConfig first, then (if `bt` is given) BacktestConfig — so exit-model
    knobs like `stop`, `target`, and `atr_mult` are sweepable alongside detection params.
    """
    if param in type(base).model_fields:
        current = getattr(base, param)
    elif bt is not None and param in _BT_FIELDS:
        current = getattr(bt, param)
    else:
        where = "detection or backtest" if bt is not None else "detection"
        raise ValueError(f"unknown {where} parameter {param!r}")
    if isinstance(current, bool):
        return raw.lower() in ("1", "true", "yes", "on")
    if isinstance(current, int):
        return int(raw)
    if isinstance(current, float):
        return float(raw)
    return raw


def split_params(combo: dict, base: DetectionConfig) -> tuple[dict, dict]:
    """Partition a combo into (detection updates, backtest updates) by field name."""
    det: dict = {}
    bt: dict = {}
    for k, v in combo.items():
        (det if k in type(base).model_fields else bt)[k] = v
    return det, bt


def combos(typed: dict[str, list]) -> list[dict]:
    """Cartesian product of {param: [values]} -> list of {param: value} dicts."""
    if not typed:
        return [{}]
    keys = list(typed)
    return [dict(zip(keys, vals)) for vals in itertools.product(*(typed[k] for k in keys))]


def split_trades(trades: list[Trade], cutoff: date) -> tuple[list[Trade], list[Trade]]:
    """Partition trades into (in-sample: entry < cutoff, out-of-sample: entry >= cutoff)."""
    in_s = [t for t in trades if t.entry_date < cutoff]
    oos = [t for t in trades if t.entry_date >= cutoff]
    return in_s, oos


def _objective_value(s: Stats, objective: str) -> float:
    val = getattr(s, objective)
    return 1e9 if val == float("inf") else float(val)


@dataclass(frozen=True)
class SweepRow:
    params: dict
    is_stats: Stats
    oos_stats: Stats
    oos_significant: bool  # OOS mean-R bootstrap CI lower bound > 0


def run_sweep(
    dfs: dict[str, pd.DataFrame],
    timeframe: str,
    base_detection: DetectionConfig,
    bt: BacktestConfig,
    typed_specs: dict[str, list],
    oos_split: float = 0.3,
    objective: str = "profit_factor",
    top: int = 10,
) -> list[SweepRow]:
    # Per-ticker out-of-sample cutoff date (last oos_split fraction of each history).
    cutoffs: dict[str, date] = {}
    for tk, df in dfs.items():
        if df.empty:
            continue
        cut = int(len(df) * (1 - oos_split))
        cut = min(max(cut, 0), len(df) - 1)
        ts = df.index[cut]
        cutoffs[tk] = ts.date() if hasattr(ts, "date") else ts

    rows: list[SweepRow] = []
    for combo in combos(typed_specs):
        det_update, bt_update = split_params(combo, base_detection)
        detection = base_detection.model_copy(update=det_update) if det_update else base_detection
        bt_combo = dataclasses.replace(bt, **bt_update) if bt_update else bt
        is_all: list[Trade] = []
        oos_all: list[Trade] = []
        for tk, df in dfs.items():
            if df.empty:
                continue
            trades = backtest_ticker(df, tk, timeframe, detection, bt_combo)
            in_s, oos = split_trades(trades, cutoffs[tk])
            is_all.extend(in_s)
            oos_all.extend(oos)
        rows.append(SweepRow(combo, summarize(is_all), summarize(oos_all), significance(oos_all).significant))

    rows.sort(key=lambda r: _objective_value(r.is_stats, objective), reverse=True)
    return rows[:top]


def format_sweep(rows: list[SweepRow], objective: str) -> str:
    if not rows:
        return "(no results)"
    param_keys = list(rows[0].params)
    pcols = "".join(f"{k[:12]:>14}" for k in param_keys)
    hdr = (
        f"{pcols}"
        f"{'IS_n':>6}{'IS_win%':>8}{'IS_R':>7}{'IS_PF':>7}"
        f"{'OOS_n':>7}{'OOS_win%':>9}{'OOS_R':>7}{'OOS_PF':>7}{'OOS_sig':>8}"
    )
    lines = [f"Ranked by in-sample {objective} (IS = in-sample, OOS = out-of-sample):", "", hdr, "-" * len(hdr)]

    def pf(x):
        return "inf" if x == float("inf") else f"{x:.2f}"

    for r in rows:
        pvals = "".join(f"{str(r.params[k]):>14}" for k in param_keys)
        i, o = r.is_stats, r.oos_stats
        lines.append(
            f"{pvals}"
            f"{i.trades:>6}{i.win_rate:>8.1f}{i.avg_r:>7.2f}{pf(i.profit_factor):>7}"
            f"{o.trades:>7}{o.win_rate:>9.1f}{o.avg_r:>7.2f}{pf(o.profit_factor):>7}"
            f"{('yes' if r.oos_significant else 'no'):>8}"
        )
    lines.append("")
    lines.append(
        "Prefer a broad plateau of good combos over a single sharp peak; confirm OOS holds up. "
        "OOS_sig = the OOS mean-R bootstrap 95% CI stays above zero (edge unlikely to be noise)."
    )
    return "\n".join(lines)
