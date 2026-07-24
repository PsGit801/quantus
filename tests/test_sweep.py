from datetime import date

import pytest

from ddbot.config import DetectionConfig
from ddbot.backtest.engine import BacktestConfig, Trade
from ddbot.backtest.sweep import (
    cast_value,
    combos,
    parse_sweep_specs,
    split_params,
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
    assert cast_value(base, "flush_atr_mult", "2.5") == 2.5        # float field
    assert isinstance(cast_value(base, "flush_atr_mult", "2.5"), float)
    assert cast_value(base, "flush_volume_window", "30") == 30     # int field
    assert isinstance(cast_value(base, "flush_volume_window", "30"), int)
    assert cast_value(base, "require_undercut", "false") is False


def test_cast_value_rejects_unknown_param():
    with pytest.raises(ValueError):
        cast_value(DetectionConfig(), "not_a_param", "1")


def test_cast_value_casts_backtest_fields_when_bt_given():
    bt = BacktestConfig()
    assert cast_value(DetectionConfig(), "stop", "atr", bt) == "atr"          # str field
    assert cast_value(DetectionConfig(), "atr_mult", "2.5", bt) == 2.5        # float field
    assert isinstance(cast_value(DetectionConfig(), "atr_mult", "2.5", bt), float)
    assert cast_value(DetectionConfig(), "max_hold_bars", "45", bt) == 45     # int field


def test_cast_value_backtest_param_rejected_without_bt():
    with pytest.raises(ValueError):
        cast_value(DetectionConfig(), "stop", "atr")  # no bt base -> unknown


def test_split_params_partitions_detection_vs_backtest():
    det, bt = split_params(
        {"flush_atr_mult": 3.0, "stop": "atr", "atr_mult": 2.5}, DetectionConfig()
    )
    assert det == {"flush_atr_mult": 3.0}
    assert bt == {"stop": "atr", "atr_mult": 2.5}


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
