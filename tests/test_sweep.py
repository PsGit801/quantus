from datetime import date

import pytest

from ddbot.config import DetectionConfig
from ddbot.backtest.engine import Trade
from ddbot.backtest.sweep import (
    cast_value,
    combos,
    parse_sweep_specs,
    split_trades,
)


def test_parse_sweep_specs():
    out = parse_sweep_specs(["volume_factor=1.0,1.5,2.0", "min_prominence_pct=0.05,0.08"])
    assert out == {"volume_factor": ["1.0", "1.5", "2.0"], "min_prominence_pct": ["0.05", "0.08"]}


def test_parse_sweep_specs_rejects_bad():
    with pytest.raises(ValueError):
        parse_sweep_specs(["volume_factor"])  # no '='


def test_cast_value_types_from_field():
    base = DetectionConfig()
    assert cast_value(base, "volume_factor", "1.5") == 1.5        # float field
    assert isinstance(cast_value(base, "volume_factor", "1.5"), float)
    assert cast_value(base, "volume_avg_window", "30") == 30       # int field
    assert isinstance(cast_value(base, "volume_avg_window", "30"), int)
    assert cast_value(base, "require_volume_confirmation", "false") is False


def test_cast_value_rejects_unknown_param():
    with pytest.raises(ValueError):
        cast_value(DetectionConfig(), "not_a_param", "1")


def test_combos_cartesian_product():
    out = combos({"a": [1, 2], "b": [10, 20]})
    assert len(out) == 4
    assert {"a": 1, "b": 10} in out and {"a": 2, "b": 20} in out


def test_combos_empty_is_single_baseline():
    assert combos({}) == [{}]


def _trade(entry_date: date) -> Trade:
    return Trade(
        ticker="T", timeframe="1d", entry_date=entry_date, entry=100.0, stop=90.0,
        target=120.0, exit_date=entry_date, exit=110.0, r_multiple=1.0, return_pct=1.0,
        bars_held=1, outcome="win",
    )


def test_split_trades_by_cutoff():
    trades = [_trade(date(2024, 1, 1)), _trade(date(2024, 6, 1)), _trade(date(2024, 12, 1))]
    in_s, oos = split_trades(trades, cutoff=date(2024, 6, 1))
    assert len(in_s) == 1 and in_s[0].entry_date == date(2024, 1, 1)
    assert len(oos) == 2  # cutoff is inclusive on the OOS side
