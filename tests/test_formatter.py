from _synthetic import TEST_CFG, flush_reclaim

from ddbot.alerts.formatter import format_signal
from ddbot.patterns.double_bottom import check_confirmation, detect, exit_options


def _confirmed(update):
    cfg = TEST_CFG.model_copy(update=update)
    df = flush_reclaim()
    p = check_confirmation(detect(df, "T", "1d", cfg)[0], df, cfg)
    return p, df, cfg


def test_exit_options_returns_both_stops():
    p, df, cfg = _confirmed({"stop_mode": "swing_low", "target_mode": "r_multiple",
                             "target_r_multiple": 1.85, "stop_atr_window": 5})
    opts = exit_options(p, df, cfg)
    labels = [o[0] for o in opts]
    assert "Swing-low stop" in labels
    assert "1×ATR stop" in labels
    # Swing-low stop = flush low - one tick.
    swing = next(o for o in opts if o[0] == "Swing-low stop")
    assert abs(swing[1] - (min(p.b1_low, p.b2_low) - 0.01)) < 1e-9
    # Each target is 1.85R above entry off its own stop.
    for _label, stop, target in opts:
        assert abs(target - (p.confirm_close + 1.85 * (p.confirm_close - stop))) < 1e-9


def test_format_signal_shows_both_options():
    p, df, cfg = _confirmed({"stop_mode": "swing_low", "target_mode": "r_multiple",
                             "target_r_multiple": 1.85, "stop_atr_window": 5})
    msg = format_signal(p, TEST_CFG and None, exit_options(p, df, cfg))
    assert "Exit options" in msg
    assert "Swing-low stop" in msg and "1×ATR stop" in msg
    assert "R:R 1.85" in msg


def test_format_signal_backward_compatible_without_options():
    p, _df, _cfg = _confirmed({"stop_mode": "swing_low", "target_mode": "r_multiple"})
    msg = format_signal(p)  # no options -> single Stop/Target lines
    assert "Stop:" in msg and "Target:" in msg
    assert "Exit options" not in msg
