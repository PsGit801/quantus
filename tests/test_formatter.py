from _synthetic import TEST_CFG, flush_reclaim

from ddbot.alerts.formatter import format_signal
from ddbot.patterns.double_bottom import check_confirmation, detect, exit_options


def _confirmed(update):
    cfg = TEST_CFG.model_copy(update=update)
    df = flush_reclaim()
    p = check_confirmation(detect(df, "T", "1d", cfg)[0], df, cfg)
    return p, df, cfg


def test_exit_options_primary_is_stored_plus_atr_alt():
    p, df, cfg = _confirmed({"stop_mode": "swing_low", "target_mode": "r_multiple",
                             "target_r_multiple": 1.85, "stop_atr_window": 5})
    opts = exit_options(p, df, cfg)
    # Primary (first) = the stored/journaled exit exactly.
    assert opts[0][0] == "Swing-low stop"
    assert opts[0][1] == p.stop_reference and opts[0][2] == p.target
    assert abs(opts[0][1] - (min(p.b1_low, p.b2_low) - 0.01)) < 1e-9
    # Second = the 1xATR alternative, clearly labelled.
    assert opts[1][0] == "1×ATR stop (alt)"
    # Each target is 1.85R above entry off its own stop.
    for _label, stop, target in opts:
        assert abs(target - (p.confirm_close + 1.85 * (p.confirm_close - stop))) < 1e-9


def test_exit_options_primary_follows_config_stop_mode():
    # With an ATR stop configured, the primary reflects it and the swing-low is the alt.
    p, df, cfg = _confirmed({"stop_mode": "atr", "stop_atr_mult": 2.0, "stop_atr_window": 5,
                             "target_mode": "r_multiple", "target_r_multiple": 1.85})
    opts = exit_options(p, df, cfg)
    assert opts[0][0] == "2×ATR stop"
    assert opts[0][1] == p.stop_reference and opts[0][2] == p.target  # the stored exit
    assert opts[1][0] == "Swing-low stop (alt)"


def test_format_signal_shows_both_options():
    p, df, cfg = _confirmed({"stop_mode": "swing_low", "target_mode": "r_multiple",
                             "target_r_multiple": 1.85, "stop_atr_window": 5})
    msg = format_signal(p, None, exit_options(p, df, cfg))
    assert "Exit options" in msg
    assert "Swing-low stop" in msg and "1×ATR stop (alt)" in msg
    assert "target = 1.85R" in msg          # R stated once in the heading
    assert "risk" in msg and "/sh" in msg   # per-option risk-per-share differs


def test_format_signal_backward_compatible_without_options():
    p, _df, _cfg = _confirmed({"stop_mode": "swing_low", "target_mode": "r_multiple"})
    msg = format_signal(p)  # no options -> single Stop/Target lines
    assert "Stop:" in msg and "Target:" in msg
    assert "Exit options" not in msg
