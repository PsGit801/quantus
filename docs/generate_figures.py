"""Generate sample figures for the Quantus design PDF.

Produces docs/figures/*.png. The real ones fetch from Yahoo; each figure is isolated
in try/except so one failure doesn't block the rest.

Run: PYTHONPATH=src .venv/bin/python docs/generate_figures.py
"""

from __future__ import annotations

import os
import shutil

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from ddbot.backtest.engine import BacktestConfig, backtest_ticker, find_signals, simulate_trade  # noqa: E402
from ddbot.backtest.sweep import run_sweep  # noqa: E402
from ddbot.charts.chart import render  # noqa: E402
from ddbot.config import load_config  # noqa: E402
from ddbot.data.yahoo import YahooDataProvider  # noqa: E402

FIG = os.path.join(os.path.dirname(__file__), "figures")
os.makedirs(FIG, exist_ok=True)

NAVY = "#1a3d5c"
GREEN = "#2e7d32"
RED = "#c62828"
ORANGE = "#e08a1e"
GREY = "#666666"

# A high-volatility universe (these names actually produce steep capitulation flushes;
# large-caps rarely do). Used for the real detection / trade / equity / study figures.
VOLATILE = ("FOXA PLTR COIN RIVN SOFI MARA RIOT AFRM ROKU CVNA UPST SNAP HOOD DKNG "
            "TSLA NVDA AMD SMCI MSTR SHOP NET CRWD ABNB U PATH").split()


def _candle(ax, x, o, h, l, c, w=0.42):
    """Draw one OHLC candlestick at position x."""
    up = c >= o
    color = GREEN if up else RED
    ax.plot([x, x], [l, h], color=color, lw=1.4, zorder=1)                 # wick
    ax.add_patch(plt.Rectangle((x - w / 2, min(o, c)), w, abs(c - o) or 0.01,
                               facecolor=color, edgecolor=color, zorder=2))  # body


# --------------------------------------------------- 0. candlestick primer
def fig_candles():
    fig, ax = plt.subplots(figsize=(9, 5.0))

    # (1) full green bar, (2) bullish hammer, (3) long-upper-wick reject, (4) red bar
    # each: (open, high, low, close)
    specs = [
        (1.0, "Full green bar\n(closes near its high)", (100, 110, 99.5, 109.5)),
        (3.0, "Bullish hammer\n(long lower wick)",       (107, 108, 99, 107.6)),
        (5.0, "Long upper wick\n(rejected — not an entry)", (100, 110, 99.5, 102)),
        (7.0, "Red bar\n(closes below open)",            (108, 109, 99, 100)),
    ]
    for x, label, (o, h, l, c) in specs:
        _candle(ax, x, o, h, l, c, w=0.5)
        ax.text(x, 96.5, label, ha="center", va="top", fontsize=8.5, color=NAVY)

    # annotate the anatomy on the first candle
    x0, (o0, h0, l0, c0) = 1.0, (100, 110, 99.5, 109.5)
    ax.annotate("high", (x0, h0), xytext=(x0 - 1.15, h0), fontsize=8, va="center",
                arrowprops=dict(arrowstyle="->", color=GREY, lw=0.8))
    ax.annotate("close", (x0 + 0.25, c0), xytext=(x0 + 1.0, c0 + 1.2), fontsize=8, va="center",
                arrowprops=dict(arrowstyle="->", color=GREY, lw=0.8))
    ax.annotate("open", (x0 + 0.25, o0), xytext=(x0 + 1.0, o0 - 1.4), fontsize=8, va="center",
                arrowprops=dict(arrowstyle="->", color=GREY, lw=0.8))
    ax.annotate("low", (x0, l0), xytext=(x0 - 1.1, l0), fontsize=8, va="center",
                arrowprops=dict(arrowstyle="->", color=GREY, lw=0.8))
    ax.text(x0 + 0.42, (o0 + c0) / 2, "body", fontsize=8, color=GREY, va="center")
    # label the wicks on the hammer
    ax.annotate("upper wick\n(small)", (3.0, 108), xytext=(3.0, 112.5), ha="center", fontsize=7.5,
                color=GREY, arrowprops=dict(arrowstyle="->", color=GREY, lw=0.8))
    ax.annotate("lower wick\n(long = rejection\nof lower prices)", (3.0, 101), xytext=(4.35, 101.5),
                ha="left", fontsize=7.5, color=GREY,
                arrowprops=dict(arrowstyle="->", color=GREY, lw=0.8))

    ax.set_title("Reading a candlestick: body, wicks, and the four shapes that matter here",
                 fontsize=12, weight="bold", color=NAVY)
    ax.set_xlim(-0.2, 8.2)
    ax.set_ylim(90, 116)
    ax.set_ylabel("price")
    ax.set_xticks([])
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "candles.png"), dpi=130)
    plt.close(fig)
    print("candles.png")


# ------------------------------------------------------------------ 1. anatomy
def fig_anatomy():
    """Idealized flush-reclaim (bear trap): decline -> B1 -> recovery to neckline ->
    steep flush that UNDERCUTS B1 -> reclaim entry below the neckline."""
    x = np.arange(0, 22)
    y = np.array([128, 122, 116, 110, 105, 101, 100,          # decline into B1 (idx6 = 100)
                  104, 108, 111, 113,                          # recovery to interim peak (neckline)
                  110, 106, 101, 96, 92,                       # steep flush...
                  91,                                          # ...B2 undercut low (idx16 = 91 < 100)
                  99, 103, 106, 109, 112], dtype=float)        # reclaim + follow-through
    b1, peak, b2, reclaim = 6, 10, 16, 17
    neckline = 113.0
    entry = y[reclaim]              # 99, below the neckline
    stop = 84.0                     # ATR stop, below the flush
    target = neckline + (neckline - stop)

    fig, ax = plt.subplots(figsize=(9, 5.4))
    ax.plot(x, y, color=NAVY, lw=2, zorder=2)

    ax.axhline(neckline, color=ORANGE, ls="--", lw=1.4)
    ax.text(0.2, neckline + 0.7, "Neckline (resistance = the interim peak)", color=ORANGE,
            fontsize=8.5, weight="bold")
    ax.axhline(y[b1], color=GREY, ls=":", lw=1.0)
    ax.text(0.2, y[b1] + 0.6, "Bottom 1 level", color=GREY, fontsize=8)
    ax.axhline(stop, color=RED, ls=":", lw=1.2)
    ax.text(0.2, stop + 0.6, "Stop (ATR: below the flush)", color=RED, fontsize=8.5)
    ax.axhline(target, color=GREEN, ls=":", lw=1.2)
    ax.text(0.2, target + 0.7, "Target (measured move above the neckline)", color=GREEN, fontsize=8.5)

    ax.annotate("Bottom 1", (b1, y[b1]), textcoords="offset points", xytext=(-4, -26),
                ha="center", fontsize=9, weight="bold",
                arrowprops=dict(arrowstyle="->", lw=0.8))
    ax.annotate("Interim peak", (peak, y[peak]), textcoords="offset points", xytext=(0, 14),
                ha="center", fontsize=9, weight="bold",
                arrowprops=dict(arrowstyle="->", lw=0.8))
    ax.annotate("Steep flush\n(high volume)\nUNDERCUTS Bottom 1\n= the bear trap", (b2, y[b2]),
                textcoords="offset points", xytext=(-2, -12), ha="center", fontsize=8, color=RED,
                weight="bold", arrowprops=dict(arrowstyle="->", color=RED, lw=1.0))
    ax.annotate("Reclaim bar\n= ENTRY (below neckline)", (reclaim, entry),
                textcoords="offset points", xytext=(46, -6), ha="center", fontsize=8.5, color=GREEN,
                weight="bold", arrowprops=dict(arrowstyle="->", color=GREEN, lw=1.0))

    ax.set_title("Anatomy of a Flush-Reclaim (Bear-Trap) Double Bottom", fontsize=12.5,
                 weight="bold", color=NAVY)
    ax.set_xlabel("time (bars)")
    ax.set_ylabel("price")
    ax.set_ylim(80, 150)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "anatomy.png"), dpi=130)
    plt.close(fig)
    print("anatomy.png")


# ------------------------------------ shared: find a real confirmed flush-reclaim
def _find_signal_ticker(dfs, cfg, timeframe):
    """Return (ticker, df, signal) for the most recent confirmed flush-reclaim, else (None,...)."""
    best = None
    for tk, df in dfs.items():
        if df.empty:
            continue
        sigs = find_signals(df, tk, timeframe, cfg)
        if sigs:
            sig = sigs[-1]
            if best is None or sig.confirm_date > best[2].confirm_date:
                best = (tk, df, sig)
    return best if best else (None, None, None)


def _find_resolved_trade(dfs, cfg, timeframe):
    """Return (ticker, df, signal, trade) for the most recent RESOLVED trade (win/loss with
    forward bars), so the trade figure shows a real outcome — not an open trade on the last bar."""
    best = None
    for tk, df in dfs.items():
        if df.empty:
            continue
        for sig in find_signals(df, tk, timeframe, cfg):
            tr = simulate_trade(df, sig, BacktestConfig(max_hold_bars=60))
            if tr is None or tr.outcome not in ("win", "loss") or tr.bars_held < 1:
                continue
            if best is None or sig.confirm_date > best[2].confirm_date:
                best = (tk, df, sig, tr)
    return best if best else (None, None, None, None)


# ------------------------------------------------------- 2. real detection chart
def fig_detection_real(tk, df, sig):
    if sig is None:
        print("detection_real: no signal, skipped")
        return
    path = render(df, sig, FIG)
    shutil.copyfile(path, os.path.join(FIG, "detection_real.png"))
    if os.path.abspath(path) != os.path.abspath(os.path.join(FIG, "detection_real.png")):
        os.remove(path)  # drop the raw render byproduct; keep only the stable name
    print("detection_real.png", tk, sig.confirm_date)


# --------------------------------------------------------------- 3. trade figure
def fig_trade(tk, df, sig, tr):
    if sig is None or tr is None:
        print("trade: no resolved trade, skipped")
        return
    dates = [ts.date() for ts in df.index]
    j = dates.index(sig.confirm_date)
    xe = dates.index(tr.exit_date)
    lo = max(0, j - 12)
    hi = min(len(df) - 1, xe + 3)
    seg = df.iloc[lo:hi + 1]
    xs = list(range(len(seg)))

    fig, ax = plt.subplots(figsize=(9, 5.0))
    ax.plot(xs, seg["close"].to_numpy(), color=NAVY, lw=1.5, label="close")
    for lvl, c, lab in [(tr.entry, NAVY, f"entry {tr.entry:.2f}"),
                        (tr.stop, RED, f"ATR stop {tr.stop:.2f}"),
                        (tr.target, GREEN, f"measured target {tr.target:.2f}")]:
        ax.axhline(lvl, color=c, ls="--", lw=1.1)
        ax.text(0.2, lvl, lab, color=c, fontsize=8.5, va="bottom")
    ax.scatter([j - lo], [tr.entry], color=NAVY, zorder=5, s=70, marker="^", label="entry (reclaim)")
    ax.scatter([xe - lo], [tr.exit], color=(GREEN if tr.r_multiple > 0 else RED), zorder=5, s=80,
               marker="*", label="exit")
    ax.set_title(f"{tk} flush-reclaim trade — {tr.outcome.upper()}  "
                 f"({tr.r_multiple:+.2f} R, {tr.bars_held} bars)",
                 fontsize=12, weight="bold", color=NAVY)
    ax.set_xlabel("bars around the signal")
    ax.set_ylabel("price")
    ax.grid(alpha=0.25)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "trade.png"), dpi=130)
    plt.close(fig)
    print("trade.png", tk, tr.outcome, tr.r_multiple)


# ------------------------------------------------------------- 4. equity curve
def fig_equity(dfs, cfg):
    bt = BacktestConfig(max_hold_bars=60)  # default 'pattern' exit = live ATR stop + measured target
    trades = []
    for tk, df in dfs.items():
        trades.extend(backtest_ticker(df, tk, "1d", cfg, bt))
    if not trades:
        print("equity: no trades, skipped")
        return
    trades.sort(key=lambda t: t.exit_date)
    cum = np.cumsum([t.r_multiple for t in trades])
    peak = np.maximum.accumulate(cum)

    fig, ax = plt.subplots(figsize=(9, 4.6))
    xs = list(range(1, len(cum) + 1))
    ax.plot(xs, cum, color=NAVY, lw=1.8, label="cumulative R")
    ax.fill_between(xs, cum, peak, color=RED, alpha=0.15, label="drawdown")
    ax.axhline(0, color="gray", lw=0.8)
    ax.set_title(f"Backtest equity curve — volatile universe, daily "
                 f"({len(trades)} trades, total {cum[-1]:.1f} R)",
                 fontsize=12, weight="bold", color=NAVY)
    ax.set_xlabel("trade # (chronological)")
    ax.set_ylabel("cumulative R (risk units)")
    ax.grid(alpha=0.25)
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "equity.png"), dpi=130)
    plt.close(fig)
    print("equity.png", f"{cum[-1]:.1f}R")


# --------------------------------------------------- 5. exit-model study heatmap
def fig_exit_study(dfs, detection):
    """Stop-model x target-model grid, in-sample vs out-of-sample profit factor."""
    stops = [("flush_low", {}), ("reclaim_bar_low", {}),
             ("atr", {"atr_mult": 2.5}), ("atr", {"atr_mult": 3.5})]
    targets = [("neckline", {}), ("measured_move", {}), ("r_multiple", {"r_target": 2.0})]
    slabels = ["flush_low", "reclaim_bar", "atr@2.5", "atr@3.5"]
    tlabels = ["neckline", "measured", "2R"]

    is_grid = np.full((len(stops), len(targets)), np.nan)
    oos_grid = np.full((len(stops), len(targets)), np.nan)
    for r, (sname, skw) in enumerate(stops):
        for c, (tname, tkw) in enumerate(targets):
            bt = BacktestConfig(stop=sname, target=tname, max_hold_bars=60, **skw, **tkw)
            row = run_sweep(dfs, "1d", detection, bt, {}, oos_split=0.3, objective="total_r", top=1)[0]
            is_grid[r, c] = min(row.is_stats.profit_factor, 5.0)
            oos_grid[r, c] = min(row.oos_stats.profit_factor, 5.0)

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.6))
    for ax, grid, title in [(axes[0], is_grid, "In-sample profit factor"),
                            (axes[1], oos_grid, "Out-of-sample profit factor")]:
        im = ax.imshow(grid, cmap="RdYlGn", vmin=0.5, vmax=3.0, aspect="auto", origin="lower")
        ax.set_xticks(range(len(tlabels)), tlabels)
        ax.set_yticks(range(len(slabels)), slabels)
        ax.set_xlabel("target model")
        ax.set_ylabel("stop model")
        ax.set_title(title, fontsize=11, weight="bold", color=NAVY)
        for r in range(len(slabels)):
            for c in range(len(tlabels)):
                v = grid[r, c]
                ax.text(c, r, "-" if np.isnan(v) else f"{v:.1f}", ha="center", va="center",
                        fontsize=8, color="black")
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.suptitle("Exit-model study — profit factor by stop model x target model (greener = better)",
                 fontsize=10.5, color=NAVY)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(os.path.join(FIG, "exit_study.png"), dpi=130)
    plt.close(fig)
    print("exit_study.png")


def main():
    cfg = load_config(os.path.join(os.path.dirname(__file__), "..", "config", "config.yaml"))
    provider = YahooDataProvider(drop_forming_bar=cfg.drop_forming_bar)

    for fn in (fig_candles, fig_anatomy):
        try:
            fn()
        except Exception as e:
            print(f"{fn.__name__} failed:", e)

    # Real figures fetch the volatile universe once (daily for equity/study, and both
    # timeframes so the detection/trade figure can pick a clean weekly flush-reclaim).
    dfs_d = {}
    for tk in VOLATILE:
        try:
            d = provider.get_ohlcv(tk, "1d", 2000)
            if not d.empty:
                dfs_d[tk] = d
        except Exception as e:
            print(f"fetch {tk} 1d failed:", e)

    dfs_w = {}
    for tk in VOLATILE:
        try:
            w = provider.get_ohlcv(tk, "1wk", 600)
            if not w.empty:
                dfs_w[tk] = w
        except Exception as e:
            print(f"fetch {tk} 1wk failed:", e)

    # Prefer a weekly signal (cleaner, higher timeframe) for the detection/trade figure.
    tk, df, sig = _find_signal_ticker(dfs_w, cfg.detection, "1wk")
    tf = "1wk"
    if sig is None:
        tk, df, sig = _find_signal_ticker(dfs_d, cfg.detection, "1d")
        tf = "1d"
    try:
        fig_detection_real(tk, df, sig)
    except Exception as e:
        print("detection_real failed:", e)

    # The trade figure needs a RESOLVED trade (weekly preferred, else daily).
    ttk, tdf, tsig, ttr = _find_resolved_trade(dfs_w, cfg.detection, "1wk")
    if tsig is None:
        ttk, tdf, tsig, ttr = _find_resolved_trade(dfs_d, cfg.detection, "1d")
    try:
        fig_trade(ttk, tdf, tsig, ttr)
    except Exception as e:
        print("trade failed:", e)
    try:
        fig_equity(dfs_d, cfg.detection)
    except Exception as e:
        print("equity failed:", e)
    try:
        fig_exit_study(dfs_d, cfg.detection)
    except Exception as e:
        print("exit_study failed:", e)


if __name__ == "__main__":
    main()
