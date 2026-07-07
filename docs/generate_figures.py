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
from ddbot.backtest.sweep import combos  # noqa: E402
from ddbot.charts.chart import render  # noqa: E402
from ddbot.config import load_config  # noqa: E402
from ddbot.data.yahoo import YahooDataProvider  # noqa: E402
from ddbot.patterns.double_bottom import check_confirmation, detect  # noqa: E402
from ddbot.patterns.base import PatternState  # noqa: E402

FIG = os.path.join(os.path.dirname(__file__), "figures")
os.makedirs(FIG, exist_ok=True)

NAVY = "#1a3d5c"
GREEN = "#2e7d32"
RED = "#c62828"
ORANGE = "#e08a1e"


# ------------------------------------------------------------------ 1. anatomy
def fig_anatomy():
    # Idealized W: decline -> B1 -> peak(neckline) -> B2 -> breakout.
    x = np.arange(0, 22)
    y = np.array([128, 122, 116, 110, 105, 101, 100, 104, 108, 111, 112,
                  110, 107, 104, 102, 100.5, 103, 108, 113, 116, 118, 120], dtype=float)
    neckline = 112.0
    stop = 99.0
    target = neckline + (neckline - stop)

    fig, ax = plt.subplots(figsize=(9, 5.2))
    ax.plot(x, y, color=NAVY, lw=2)

    ax.axhline(neckline, color=ORANGE, ls="--", lw=1.4)
    ax.text(0.2, neckline + 0.6, "Neckline (resistance)", color=ORANGE, fontsize=9, weight="bold")
    ax.axhline(stop, color=RED, ls=":", lw=1.2)
    ax.text(0.2, stop - 2.0, "Stop (below bottoms)", color=RED, fontsize=9)
    ax.axhline(target, color=GREEN, ls=":", lw=1.2)
    ax.text(0.2, target + 0.6, "Target = neckline + (neckline - bottom)  [measured move]",
            color=GREEN, fontsize=9)

    for xi, label, dy in [(6, "Bottom 1", -3.2), (15, "Bottom 2", -3.2), (10, "Interim peak", 1.0)]:
        ax.annotate(label, (xi, y[xi]), textcoords="offset points", xytext=(0, dy * 6),
                    ha="center", fontsize=9, weight="bold",
                    arrowprops=dict(arrowstyle="->", color="black", lw=0.8))

    ax.annotate("Breakout candle\n(green, above neckline,\non strong volume)", (18, y[18]),
                textcoords="offset points", xytext=(18, -6), ha="center", fontsize=8.5,
                color=GREEN, weight="bold",
                arrowprops=dict(arrowstyle="->", color=GREEN, lw=1.0))

    # prominence bracket
    ax.annotate("", (2.0, stop), (2.0, neckline), arrowprops=dict(arrowstyle="<->", color="gray"))
    ax.text(2.4, (stop + neckline) / 2, "prominence", rotation=90, va="center", fontsize=8, color="gray")

    ax.set_title("Anatomy of a Double Bottom", fontsize=13, weight="bold", color=NAVY)
    ax.set_xlabel("time (bars)")
    ax.set_ylabel("price")
    ax.set_ylim(90, 132)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "anatomy.png"), dpi=130)
    plt.close(fig)
    print("anatomy.png")


# ---------------------------------------------------- shared: a real AAPL signal
def _latest_signal(df, cfg, ticker="AAPL", tf="1d"):
    sigs = find_signals(df, ticker, tf, cfg)
    return sigs[-1] if sigs else None


# ------------------------------------------------------- 2. real detection chart
def fig_detection_real(df, cfg):
    sig = _latest_signal(df, cfg)
    if sig is None:
        print("detection_real: no signal, skipped")
        return
    path = render(df, sig, FIG)
    shutil.copyfile(path, os.path.join(FIG, "detection_real.png"))
    print("detection_real.png", sig.confirm_date)
    return sig


# --------------------------------------------------------------- 3. trade figure
def fig_trade(df, cfg, sig):
    if sig is None:
        print("trade: no signal, skipped")
        return
    bt = BacktestConfig(max_hold_bars=60)
    tr = simulate_trade(df, sig, bt)
    if tr is None:
        print("trade: untradeable, skipped")
        return
    dates = [ts.date() for ts in df.index]
    j = dates.index(sig.confirm_date)
    xe = dates.index(tr.exit_date)
    lo = max(0, j - 20)
    hi = min(len(df) - 1, xe + 3)
    seg = df.iloc[lo:hi + 1]
    xs = list(range(len(seg)))

    fig, ax = plt.subplots(figsize=(9, 5.0))
    ax.plot(xs, seg["close"].to_numpy(), color=NAVY, lw=1.5, label="close")
    for lvl, c, lab in [(tr.entry, NAVY, f"entry {tr.entry:.2f}"),
                        (tr.stop, RED, f"stop {tr.stop:.2f}"),
                        (tr.target, GREEN, f"target {tr.target:.2f}")]:
        ax.axhline(lvl, color=c, ls="--", lw=1.1)
        ax.text(0.2, lvl, lab, color=c, fontsize=8.5, va="bottom")
    ax.scatter([j - lo], [tr.entry], color=NAVY, zorder=5, s=60, marker="^", label="entry")
    ax.scatter([xe - lo], [tr.exit], color=(GREEN if tr.r_multiple > 0 else RED), zorder=5, s=70,
               marker="*", label="exit")
    ax.set_title(f"AAPL trade — {tr.outcome.upper()}  ({tr.r_multiple:+.2f} R, {tr.bars_held} bars)",
                 fontsize=12, weight="bold", color=NAVY)
    ax.set_xlabel("bars around the signal")
    ax.set_ylabel("price")
    ax.grid(alpha=0.25)
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "trade.png"), dpi=130)
    plt.close(fig)
    print("trade.png", tr.outcome, tr.r_multiple)


# ------------------------------------------------------------- 4. equity curve
def fig_equity(dfs, cfg):
    bt = BacktestConfig(max_hold_bars=60)
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
    ax.set_title(f"Backtest equity curve — Mag7 daily ({len(trades)} trades, total {cum[-1]:.1f} R)",
                 fontsize=12, weight="bold", color=NAVY)
    ax.set_xlabel("trade # (chronological)")
    ax.set_ylabel("cumulative R")
    ax.grid(alpha=0.25)
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "equity.png"), dpi=130)
    plt.close(fig)
    print("equity.png", f"{cum[-1]:.1f}R")


# --------------------------------------------------------------- 5. sweep heatmap
def fig_sweep_heatmap(dfs, base_detection):
    vfs = [1.0, 1.25, 1.5, 1.75, 2.0]
    mps = [0.05, 0.065, 0.08]
    bt = BacktestConfig(max_hold_bars=60)

    # per-ticker OOS cutoff (last 30%)
    cutoffs = {}
    for tk, df in dfs.items():
        if df.empty:
            continue
        c = min(max(int(len(df) * 0.7), 0), len(df) - 1)
        ts = df.index[c]
        cutoffs[tk] = ts.date() if hasattr(ts, "date") else ts

    def pf(trades):
        gw = sum(t.r_multiple for t in trades if t.r_multiple > 0)
        gl = -sum(t.r_multiple for t in trades if t.r_multiple <= 0)
        if gl == 0:
            return np.nan if not trades else 3.0  # cap/na for display
        return gw / gl

    is_grid = np.full((len(mps), len(vfs)), np.nan)
    oos_grid = np.full((len(mps), len(vfs)), np.nan)
    for r, mp in enumerate(mps):
        for c, vf in enumerate(vfs):
            det = base_detection.model_copy(update={"volume_factor": vf, "min_prominence_pct": mp})
            is_t, oos_t = [], []
            for tk, df in dfs.items():
                trs = backtest_ticker(df, tk, "1d", det, bt)
                is_t += [t for t in trs if t.entry_date < cutoffs[tk]]
                oos_t += [t for t in trs if t.entry_date >= cutoffs[tk]]
            is_grid[r, c] = min(pf(is_t), 4.0)
            oos_grid[r, c] = min(pf(oos_t), 4.0)

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.4))
    for ax, grid, title in [(axes[0], is_grid, "In-sample profit factor"),
                            (axes[1], oos_grid, "Out-of-sample profit factor")]:
        im = ax.imshow(grid, cmap="RdYlGn", vmin=0.5, vmax=3.0, aspect="auto", origin="lower")
        ax.set_xticks(range(len(vfs)), [str(v) for v in vfs])
        ax.set_yticks(range(len(mps)), [str(m) for m in mps])
        ax.set_xlabel("volume_factor")
        ax.set_ylabel("min_prominence_pct")
        ax.set_title(title, fontsize=11, weight="bold", color=NAVY)
        for r in range(len(mps)):
            for c in range(len(vfs)):
                val = grid[r, c]
                ax.text(c, r, "-" if np.isnan(val) else f"{val:.1f}", ha="center", va="center",
                        fontsize=8, color="black")
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.suptitle("Parameter sweep — profit factor (higher = greener). Compare IS vs OOS to spot overfitting.",
                 fontsize=10.5, color=NAVY)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(os.path.join(FIG, "sweep_heatmap.png"), dpi=130)
    plt.close(fig)
    print("sweep_heatmap.png")


def main():
    cfg = load_config(os.path.join(os.path.dirname(__file__), "..", "config", "config.yaml"))
    provider = YahooDataProvider(drop_forming_bar=cfg.drop_forming_bar)

    try:
        fig_anatomy()
    except Exception as e:
        print("anatomy failed:", e)

    dfs = {}
    for tk in cfg.tickers:
        try:
            dfs[tk] = provider.get_ohlcv(tk, "1d", 1000)
        except Exception as e:
            print(f"fetch {tk} failed:", e)

    aapl = dfs.get("AAPL")
    sig = None
    if aapl is not None and not aapl.empty:
        try:
            sig = fig_detection_real(aapl, cfg.detection)
        except Exception as e:
            print("detection_real failed:", e)
        try:
            fig_trade(aapl, cfg.detection, sig)
        except Exception as e:
            print("trade failed:", e)
    try:
        fig_equity(dfs, cfg.detection)
    except Exception as e:
        print("equity failed:", e)
    try:
        fig_sweep_heatmap(dfs, cfg.detection)
    except Exception as e:
        print("sweep_heatmap failed:", e)


if __name__ == "__main__":
    main()
