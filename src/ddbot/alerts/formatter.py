"""Turn a confirmed pattern into a human-readable alert message."""

from __future__ import annotations

from ..patterns.base import DoubleBottom
from ..risk import position_size


def format_signal(p: DoubleBottom, risk=None) -> str:
    lines = [
        "🟢 *Double Bottom — flush reclaim*",
        f"*{p.ticker}* ({p.timeframe})",
        "",
        f"Bottom 1: {p.b1_low:.2f} on {p.b1_date}",
        f"Flush low (B2): {p.b2_low:.2f} on {p.b2_date}",
        f"Reclaim close (entry): {p.confirm_close:.2f} on {p.confirm_date}",
        f"Neckline (target): {p.neckline:.2f}",
        f"Stop (below flush low): {p.stop_reference:.2f}",
    ]

    if p.confirm_close is not None:
        risk_per_share = p.confirm_close - p.stop_reference
        reward = p.neckline - p.confirm_close
        if risk_per_share > 0:
            lines.append(f"Reward:risk to target: {reward / risk_per_share:.2f}R")

    if risk is not None and p.confirm_close is not None:
        s = position_size(
            entry=p.confirm_close,
            stop=p.stop_reference,
            equity=risk.account_equity,
            risk_pct=risk.risk_per_trade_pct,
            max_position_pct=risk.max_position_pct,
        )
        if s.shares > 0:
            lines += [
                "",
                (f"Suggested size (risk {risk.risk_per_trade_pct:.0%} of "
                 f"${risk.account_equity:,.0f}): *{s.shares} shares*"),
                f"  ≈ ${s.dollar_risk:,.0f} risk · ${s.position_value:,.0f} position "
                f"({s.notional_pct:.0%} of equity)" + ("  [capped]" if s.capped else ""),
            ]

    lines += [
        "",
        ("_Discretionary setup — the flush-reclaim has no validated mechanical edge "
         "(breaks even out-of-sample). Review the chart before acting._"),
    ]
    return "\n".join(lines)
