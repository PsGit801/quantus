"""CLI: python -m ddbot.backtest — backtest the double-bottom strategy over history."""

from __future__ import annotations

import argparse
import csv
import dataclasses

from ..config import load_config
from ..data.yahoo import YahooDataProvider
from ..mtf import is_uptrend
from .engine import BacktestConfig, backtest_ticker
from .metrics import equity_curve, format_report, summarize
from .sweep import cast_value, format_sweep, parse_sweep_specs, run_sweep
from .walkforward import anchored_oos, rolling_folds, walk_forward_report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Backtest the double-bottom strategy")
    p.add_argument("--config", default="config/config.yaml")
    p.add_argument("--tickers", nargs="*", help="override watchlist (default: config tickers)")
    p.add_argument("--timeframe", default="1d")
    p.add_argument("--history-bars", type=int, default=1000, help="bars of history to fetch")
    p.add_argument("--max-hold", type=int, default=60, help="max bars to hold a trade")
    p.add_argument("--target", choices=["pattern", "neckline", "measured_move", "r_multiple"],
                   default="pattern", help="'pattern' = the live strategy's target (default)")
    p.add_argument("--r-target", type=float, default=2.0, help="reward:risk when --target r_multiple")
    p.add_argument("--stop", choices=["pattern", "flush_low", "reclaim_bar_low", "atr"],
                   default="pattern",
                   help="'pattern' = the live strategy's stop (default); or override for research")
    p.add_argument("--atr-window", type=int, default=14, help="ATR window when --stop atr")
    p.add_argument("--atr-mult", type=float, default=1.5, help="stop = entry - mult x ATR when --stop atr")
    p.add_argument("--csv", help="write individual trades to this CSV path")
    p.add_argument(
        "--sweep", action="append", default=[],
        help="grid-search a detection param: PARAM=v1,v2,... (repeatable)",
    )
    p.add_argument("--oos-split", type=float, default=0.3, help="out-of-sample fraction (newest)")
    p.add_argument(
        "--objective", default="profit_factor",
        choices=["profit_factor", "total_r", "avg_r", "win_rate"],
        help="sweep ranking metric (in-sample)",
    )
    p.add_argument("--top", type=int, default=10, help="how many top sweep combos to show")
    p.add_argument(
        "--walk-forward", type=int, default=0, metavar="N",
        help="also report the current config across N sequential entry-date folds (0 = off)",
    )
    p.add_argument(
        "--min-fold-trades", type=int, default=10,
        help="flag walk-forward folds with fewer trades than this as low-sample",
    )
    p.add_argument("--equity", type=float, help="starting $ for a fixed-fractional equity curve")
    p.add_argument("--risk-pct", type=float, help="risk fraction per trade (default: config risk)")
    p.add_argument("--no-mtf", action="store_true", help="disable multi-timeframe confirmation")
    args = p.parse_args(argv)

    cfg = load_config(args.config)
    tickers = args.tickers or cfg.tickers
    detection = cfg.detection

    bt = BacktestConfig(
        target=args.target, r_target=args.r_target, max_hold_bars=args.max_hold,
        stop=args.stop, atr_window=args.atr_window, atr_mult=args.atr_mult,
    )
    provider = YahooDataProvider(drop_forming_bar=cfg.drop_forming_bar)

    # --- sweep mode -----------------------------------------------------------
    if args.sweep:
        typed = {
            param: [cast_value(detection, param, v) for v in vals]
            for param, vals in parse_sweep_specs(args.sweep).items()
        }
        dfs = {tk: provider.get_ohlcv(tk, args.timeframe, args.history_bars) for tk in tickers}
        rows = run_sweep(
            dfs, args.timeframe, detection, bt, typed,
            oos_split=args.oos_split, objective=args.objective, top=args.top,
        )
        print(f"\nParameter sweep — {args.timeframe}, {len(tickers)} tickers, oos={args.oos_split:.0%}\n")
        print(format_sweep(rows, args.objective))
        print()
        return 0

    # Multi-timeframe gate: for a lower timeframe, require the higher-TF uptrend (matches live).
    m = cfg.mtf
    use_mtf = m.require and not args.no_mtf and args.timeframe != m.higher_timeframe

    all_trades = []
    per_ticker = {}
    for ticker in tickers:
        df = provider.get_ohlcv(ticker, args.timeframe, args.history_bars)
        mtf_filter = None
        if use_mtf:
            hdf = provider.get_ohlcv(ticker, m.higher_timeframe, max(args.history_bars, m.sma_window * 5))
            mtf_filter = lambda d, _h=hdf: is_uptrend(_h, d, m.sma_window)
        trades = backtest_ticker(df, ticker, args.timeframe, detection, bt, mtf_filter=mtf_filter)
        per_ticker[ticker] = summarize(trades)
        all_trades.extend(trades)

    overall = summarize(all_trades)
    span = ""
    if all_trades:
        span = f"  ({min(t.entry_date for t in all_trades)} → {max(t.exit_date for t in all_trades)})"
    mtf_note = f", MTF={'on' if use_mtf else 'off'}"
    print(f"\nDouble-bottom backtest — {args.timeframe}, stop={args.stop}, target={args.target}{mtf_note}{span}\n")
    print(format_report(per_ticker, overall))
    print()

    # Dollar equity curve (fixed-fractional). Shown if --equity given, else uses config.
    start_eq = args.equity if args.equity is not None else cfg.risk.account_equity
    risk_pct = args.risk_pct if args.risk_pct is not None else cfg.risk.risk_per_trade_pct
    eq = equity_curve(all_trades, start_eq, risk_pct)
    print(
        f"Portfolio (fixed-fractional {risk_pct:.1%} risk on ${eq.start_equity:,.0f}, "
        f"sequential compounding):\n"
        f"  final ${eq.final_equity:,.0f}  |  return {eq.total_return_pct:+.1f}%  |  "
        f"CAGR {eq.cagr_pct:+.1f}%  |  max drawdown {eq.max_drawdown_pct:.1f}%\n"
        f"  (ignores slippage/commissions/dividends and concurrent-position capital limits)\n"
    )

    # Walk-forward: is the edge stable across time, or concentrated in one window?
    if args.walk_forward and all_trades:
        folds = rolling_folds(all_trades, args.walk_forward)
        anchored = anchored_oos(all_trades, args.oos_split)
        print(walk_forward_report(folds, overall, args.min_fold_trades, anchored))
        print()

    if args.csv and all_trades:
        fields = [f.name for f in dataclasses.fields(all_trades[0])]
        with open(args.csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for t in all_trades:
                w.writerow(dataclasses.asdict(t))
        print(f"wrote {len(all_trades)} trades to {args.csv}")

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
