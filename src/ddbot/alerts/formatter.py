"""Turn a confirmed pattern into a human-readable alert message."""

from __future__ import annotations

from ..patterns.base import DoubleBottom
from ..risk import position_size


def format_signal(p: DoubleBottom, risk=None, options=None) -> str:
    """Render the alert. `options` is an optional list of (label, stop, target) exit
    choices (see patterns.double_bottom.exit_options); when given, both stop methods are
    shown so the trader picks per trade, and sizing uses the first (primary) option.
    Without it, the single configured stop/target is shown (backward-compatible)."""
    lines = [
        "🟢 *Double Bottom — flush reclaim*",
        f"*{p.ticker}* ({p.timeframe})",
        "",
        f"Bottom 1: {p.b1_low:.2f} on {p.b1_date}",
        f"Flush low (B2): {p.b2_low:.2f} on {p.b2_date}",
        f"Reclaim close (entry): {p.confirm_close:.2f} on {p.confirm_date}",
        f"Neckline: {p.neckline:.2f}",
    ]

    sizing_stop = p.stop_reference  # which stop position sizing uses
    if options:
        entry = p.confirm_close
        # R:R is the same for every option by construction (target = entry + R x risk),
        # so state it once; per option show the differing stop, target, and risk/share.
        first_stop, first_target = options[0][1], options[0][2]
        rr = (first_target - entry) / (entry - first_stop) if (
            entry is not None and entry - first_stop > 0
        ) else 0.0
        lines.append("")
        lines.append(f"*Exit options* (target = {rr:.2f}R; first is journaled, pick per your plan):")
        for label, stop, target in options:
            risk_ps = entry - stop if entry is not None else 0.0
            lines.append(f"  • {label}: stop {stop:.2f}  →  target {target:.2f}  (risk {risk_ps:.2f}/sh)")
        sizing_stop = options[0][1]  # size off the primary (journaled) option
    else:
        lines.append(f"Target: {p.target:.2f}")
        lines.append(f"Stop: {p.stop_reference:.2f}")
        if p.confirm_close is not None:
            risk_per_share = p.confirm_close - p.stop_reference
            reward = p.target - p.confirm_close
            if risk_per_share > 0:
                lines.append(f"Reward:risk to target: {reward / risk_per_share:.2f}R")

    if risk is not None and p.confirm_close is not None:
        s = position_size(
            entry=p.confirm_close,
            stop=sizing_stop,
            equity=risk.account_equity,
            risk_pct=risk.risk_per_trade_pct,
            max_position_pct=risk.max_position_pct,
        )
        if s.shares > 0:
            size_note = "journaled stop, " if options else ""
            lines += [
                "",
                (f"Suggested size ({size_note}risk {risk.risk_per_trade_pct:.0%} of "
                 f"${risk.account_equity:,.0f}): *{s.shares} shares*"),
                f"  ≈ ${s.dollar_risk:,.0f} risk · ${s.position_value:,.0f} position "
                f"({s.notional_pct:.0%} of equity)" + ("  [capped]" if s.capped else ""),
            ]

    footer = (
        "_First (journaled) exit is the backtested default and what the digest scores; the "
        "(alt) is a discretionary variant it does not track. "
        if options else
        "_Stop and target per the configured exit model. "
    )
    lines += [
        "",
        footer + "Edge rests on a modest sample; still discretionary — review the chart "
        "before acting._",
    ]
    return "\n".join(lines)
