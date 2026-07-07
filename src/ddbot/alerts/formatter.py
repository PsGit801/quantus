"""Turn a confirmed pattern into a human-readable alert message."""

from __future__ import annotations

from ..patterns.base import DoubleBottom
from ..risk import position_size


def format_signal(p: DoubleBottom, risk=None) -> str:
    lines = [
        "🟢 *Double Bottom confirmed*",
        f"*{p.ticker}* ({p.timeframe})",
        "",
        f"Bottom 1: {p.b1_low:.2f} on {p.b1_date}",
        f"Bottom 2: {p.b2_low:.2f} on {p.b2_date}",
        f"Neckline: {p.neckline:.2f}",
        f"Breakout close: {p.confirm_close:.2f} on {p.confirm_date}",
        f"Stop ref (below bottoms): {p.stop_reference:.2f}",
    ]

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
        "_Manual confirmation advised — pattern detection is probabilistic._",
    ]
    return "\n".join(lines)
