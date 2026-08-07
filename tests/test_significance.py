from datetime import date

from ddbot.backtest.engine import Trade
from ddbot.backtest.metrics import (
    format_significance,
    r_distribution,
    significance,
)


def _trade(r: float) -> Trade:
    return Trade(
        ticker="T", timeframe="1d", entry_date=date(2024, 1, 1), entry=100.0, stop=90.0,
        target=120.0, exit_date=date(2024, 1, 2), exit=100.0 + 10.0 * r, r_multiple=r,
        return_pct=r, bars_held=1, outcome="win" if r > 0 else "loss",
    )


def test_r_distribution_percentiles():
    d = r_distribution([_trade(r) for r in (-1.0, 0.0, 1.0, 2.0, 3.0)])
    assert d.n == 5
    assert d.r_min == -1.0 and d.r_max == 3.0
    assert d.r_median == 1.0
    assert d.r_p25 == 0.0 and d.r_p75 == 2.0


def test_r_distribution_empty():
    d = r_distribution([])
    assert d.n == 0 and d.r_min == 0.0 and d.r_max == 0.0


def test_significance_strong_positive_is_significant():
    sig = significance([_trade(2.0) for _ in range(40)])
    assert sig.n == 40
    assert sig.significant is True          # all-positive -> CI well above 0
    assert sig.adequate_sample is True      # n >= 30
    assert sig.ci_low > 0


def test_significance_small_sample_flagged_inadequate():
    sig = significance([_trade(1.0) for _ in range(3)])
    assert sig.significant is True          # 3 wins -> CI is [1, 1]
    assert sig.adequate_sample is False     # but n < 30
    assert sig.ci_low == sig.ci_high == 1.0


def test_significance_mixed_around_zero_not_significant():
    sig = significance([_trade(r) for r in (-1.0, -1.0, 1.0, 1.0)])
    assert sig.mean_r == 0.0
    assert sig.significant is False         # CI straddles zero
    assert sig.ci_low < 0 < sig.ci_high


def test_significance_is_deterministic():
    trades = [_trade(r) for r in (-1.0, 0.5, 2.0, -0.3, 1.2, 0.8)]
    a = significance(trades, seed=0)
    b = significance(trades, seed=0)
    assert a == b                            # same seed -> identical CI


def test_significance_empty():
    sig = significance([])
    assert sig.n == 0 and sig.significant is False and sig.adequate_sample is False


def test_format_significance_contains_key_lines():
    trades = [_trade(r) for r in (1.0, 2.0, -1.0, 0.5)]
    text = format_significance(r_distribution(trades), significance(trades))
    assert "R percentiles:" in text
    assert "95% CI" in text
    assert "Verdict:" in text


def test_format_significance_empty():
    assert "no trades" in format_significance(r_distribution([]), significance([]))
