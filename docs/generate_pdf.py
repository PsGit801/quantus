"""Generate the Quantus design & concepts PDF (reportlab, pure-Python).

Run: .venv/bin/python docs/generate_pdf.py  ->  docs/Quantus_Design_Document.pdf
Regenerate any time; content is hand-maintained here.
"""

from __future__ import annotations

import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Image,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "Quantus_Design_Document.pdf")
FIG = os.path.join(HERE, "figures")

styles = getSampleStyleSheet()
BODY = ParagraphStyle("body", parent=styles["BodyText"], fontSize=10, leading=14, spaceAfter=6)
H1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=16, spaceBefore=6, spaceAfter=8,
                    textColor=colors.HexColor("#1a3d5c"))
H2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12.5, spaceBefore=10, spaceAfter=5,
                    textColor=colors.HexColor("#2a5d8c"))
CODE = ParagraphStyle("code", parent=styles["Code"], fontSize=8.2, leading=10.5,
                      backColor=colors.HexColor("#f2f4f7"), borderPadding=6, leftIndent=4, spaceAfter=8)
TITLE = ParagraphStyle("title", parent=styles["Title"], fontSize=26, leading=30,
                       textColor=colors.HexColor("#1a3d5c"))
SUB = ParagraphStyle("sub", parent=styles["Normal"], fontSize=12, alignment=TA_CENTER,
                     textColor=colors.HexColor("#555555"))
CENTER = ParagraphStyle("center", parent=BODY, alignment=TA_CENTER)

story = []


def h1(t):
    story.append(Paragraph(t, H1))


def h2(t):
    story.append(Paragraph(t, H2))


def p(t):
    story.append(Paragraph(t, BODY))


def bullets(items):
    story.append(ListFlowable(
        [ListItem(Paragraph(i, BODY), leftIndent=10) for i in items],
        bulletType="bullet", start="•", leftIndent=12,
    ))
    story.append(Spacer(1, 4))


def code(t):
    story.append(Preformatted(t.strip("\n"), CODE))


def table(data, col_widths=None):
    t = Table(data, colWidths=col_widths, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3d5c")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f4f7")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t)
    story.append(Spacer(1, 8))


def spacer(h=8):
    story.append(Spacer(1, h))


CAPTION = ParagraphStyle("caption", parent=BODY, fontSize=8.5, leading=11,
                         textColor=colors.HexColor("#555555"), alignment=TA_CENTER, spaceBefore=2)


def image(filename, caption, max_w=15.5 * cm):
    """Embed a figure scaled to fit width (aspect preserved); skip if missing."""
    path = os.path.join(FIG, filename)
    if not os.path.exists(path):
        story.append(Paragraph(f"<i>[figure {filename} not generated]</i>", CAPTION))
        return
    iw, ih = ImageReader(path).getSize()
    w = min(max_w, iw)
    h = w * ih / iw
    story.append(KeepTogether([
        Spacer(1, 4),
        Image(path, width=w, height=h),
        Paragraph(caption, CAPTION),
        Spacer(1, 6),
    ]))


# ============================== COVER =========================================
story.append(Spacer(1, 4 * cm))
story.append(Paragraph("Quantus", TITLE))
story.append(Spacer(1, 0.3 * cm))
story.append(Paragraph("Double-Bottom Chart-Pattern Scanner &amp; Alert Bot", SUB))
story.append(Paragraph("Design, Backend Architecture &amp; Trading Concepts", SUB))
story.append(Spacer(1, 1.2 * cm))
story.append(Paragraph("Technical Design Document &mdash; generated 2026-07-06", CENTER))
story.append(Spacer(1, 1.5 * cm))
story.append(Paragraph(
    "Quantus watches a configurable watchlist (the Magnificent 7 by default) on the daily and weekly "
    "timeframes, algorithmically detects the <b>double-bottom</b> reversal pattern, waits for a "
    "volume-backed bullish breakout above the neckline to confirm it, and then pushes an alert &mdash; "
    "with an annotated candlestick chart &mdash; to Telegram and Discord. It includes an interactive "
    "Telegram bot for managing the watchlist and a full backtesting engine (with parameter sweeps and "
    "out-of-sample validation) for measuring the strategy's historical edge.", BODY))
story.append(PageBreak())

# ============================== 1. OVERVIEW ===================================
h1("1. What Quantus Is")
p("Quantus is a personal, single-user quantitative trading <b>alert</b> system. It does not place "
  "trades; it surfaces high-quality technical setups and leaves the execution decision to the human. "
  "The design goal is a clean, testable, deterministic pipeline that a trader can trust, inspect, and "
  "tune against historical data.")
h2("At a glance")
bullets([
    "<b>Data:</b> free end-of-day OHLCV from Yahoo Finance (via the <font face='Courier'>yfinance</font> library).",
    "<b>Universe:</b> a watchlist stored in SQLite, seeded from config (AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA), editable live from Telegram.",
    "<b>Timeframes:</b> daily and weekly, scanned independently.",
    "<b>Pattern:</b> double bottom, confirmed by a bullish, volume-backed close above the neckline.",
    "<b>Delivery:</b> Telegram + Discord, each alert carrying an annotated chart image.",
    "<b>Scheduling:</b> a once-daily scan run by the hermes cron scheduler; an always-on listener for instant Telegram interaction.",
    "<b>Validation:</b> a walk-forward backtester and a parameter sweep with in-sample / out-of-sample splitting.",
])
p("The codebase is Python 3.11, organized as the <font face='Courier'>ddbot</font> package, with 53 "
  "automated tests. Every component is behind an interface (data provider, alerter, pattern) so pieces "
  "can be swapped without rewrites.")

# ============================== 2. CONCEPTS ===================================
h1("2. Fundamentals: The Concepts Behind the Bot")
p("This section explains the technical-analysis and quantitative ideas the bot relies on, so the logic "
  "in later sections is meaningful.")

h2("2.1 The double bottom (and the neckline)")
p("A <b>double bottom</b> is a bullish reversal pattern shaped like a 'W'. After a decline, price "
  "makes a low (Bottom 1), rebounds to an interim peak, falls again to roughly the same level "
  "(Bottom 2), then rallies. The two bottoms mark a support level buyers defended twice. The "
  "<b>neckline</b> is the interim peak between the bottoms &mdash; the resistance that price must break "
  "to confirm the reversal. A close above the neckline signals that buyers have overwhelmed the sellers "
  "who were capping the rebound.")
image("anatomy.png", "Figure 1. The anatomy of a double bottom: two bottoms at a shared support, the "
      "neckline (resistance) between them, prominence (depth), and the confirming breakout. The stop "
      "sits below the bottoms; the measured-move target projects the pattern height above the neckline.")

h2("2.2 Swing points (fractals)")
p("To find the bottoms and the neckline objectively, the bot detects <b>swing points</b>. A bar is a "
  "<b>swing low</b> if its low is the lowest within a symmetric window of <font face='Courier'>k</font> "
  "bars on each side (a 'fractal'); a swing high is the mirror image. This turns a subjective visual "
  "pattern into a precise, reproducible rule.")

h2("2.3 Prominence")
p("Not every wiggle is a real 'W'. <b>Prominence</b> measures how far the neckline sits above the "
  "bottoms as a percentage. Requiring a minimum prominence (default 5%) discards shallow, sideways "
  "noise and keeps structures with genuine depth &mdash; the single most effective false-positive filter.")

h2("2.4 Confirmation and no-repaint discipline")
p("A pattern is only a <b>candidate</b> until price actually breaks out. Confirmation requires the first "
  "candle after Bottom 2 to close above the neckline (plus a small buffer) as a green (bullish) candle. "
  "Crucially, the bot acts only on <b>closed</b> bars &mdash; the still-forming current bar is dropped "
  "&mdash; because a forming bar can 'repaint' (change) before it closes. This avoids the classic "
  "backtest-vs-live discrepancy where a strategy looks good only because it peeked at data that did not "
  "yet exist.")

h2("2.5 Volume confirmation")
p("A breakout on thin volume often fizzles. The bot requires the breakout candle's volume to be at "
  "least a multiple (<font face='Courier'>volume_factor</font>) of the recent average volume. Genuine "
  "reversals tend to attract participation; the volume gate filters low-conviction breaks.")

h2("2.6 Measuring an edge: R-multiples, expectancy, profit factor, drawdown")
bullets([
    "<b>R (risk unit):</b> the distance from entry to the protective stop. A trade that gains twice its "
    "risk is +2R; one that hits the stop is -1R. Expressing results in R makes trades comparable across "
    "prices and position sizes.",
    "<b>Expectancy (average R):</b> the mean R per trade &mdash; the average profit (in risk units) you "
    "expect from each signal. Positive expectancy is the definition of an edge.",
    "<b>Win rate:</b> the fraction of trades that are profitable. High win rate with small average R is "
    "common for target-based exits and is not automatically good or bad on its own.",
    "<b>Profit factor:</b> gross winning R divided by gross losing R. Above 1.0 is profitable; ~1.3 is "
    "modest, ~2+ is strong.",
    "<b>Max drawdown:</b> the largest peak-to-trough drop of the cumulative-R equity curve &mdash; a "
    "measure of the pain an approach inflicts before recovering.",
])

h2("2.7 Walk-forward, in-sample vs out-of-sample, and overfitting")
p("<b>Overfitting</b> (curve-fitting) is tuning parameters until they look perfect on past data, only "
  "to fail live. Two defenses are built in. <b>Walk-forward</b> testing replays history bar by bar, only "
  "ever using data that existed at each moment &mdash; no look-ahead. <b>Out-of-sample (OOS)</b> "
  "validation reserves the most recent slice of history, tunes on the older <b>in-sample</b> portion, "
  "and checks whether the chosen settings still work on the untouched OOS slice. A setting whose edge "
  "vanishes out-of-sample was overfit and is discarded.")
story.append(PageBreak())

# ============================== 3. ARCHITECTURE ===============================
h1("3. Backend Architecture")
p("The system is a set of small, single-responsibility modules connected by a linear data pipeline. "
  "The same detection code powers the live scanner and the backtester, so what you measure is what you "
  "trade.")

h2("3.1 Data-flow pipeline (daily scan)")
code(
    "hermes cron (17:00)\n"
    "      |\n"
    "      v\n"
    "  ddbot.run  ->  YahooDataProvider          (fetch closed OHLCV bars)\n"
    "      |            |\n"
    "      |            v\n"
    "      |         detect()                     (swings -> candidate W's -> neckline\n"
    "      |            |                          + prominence + prior-downtrend)\n"
    "      |            v\n"
    "      |         dedupe_by_neckline()         (one setup per resistance level)\n"
    "      |            |\n"
    "      |            v\n"
    "      |         PatternStore (SQLite)        (persist pending patterns; dedup/idempotency)\n"
    "      |            |\n"
    "      |            v\n"
    "      |         check_confirmation()         (breakout + green + volume, closed bars only)\n"
    "      |            |\n"
    "      |            v\n"
    "      |         render chart (mplfinance) -> CompositeAlerter -> Telegram + Discord\n"
    "      v\n"
    "   exit (idempotent: a confirmed setup is alerted exactly once)"
)

h2("3.2 Module map")
table([
    ["Module", "Responsibility"],
    ["data/yahoo.py", "Fetch OHLCV from Yahoo; drop the forming bar; symbol validation/normalization."],
    ["patterns/swings.py", "Swing-high / swing-low (fractal) detection."],
    ["patterns/double_bottom.py", "detect(), dedupe_by_neckline(), check_confirmation() (incl. volume gate)."],
    ["patterns/base.py", "DoubleBottom data model, PatternState, stable pattern_id, stop reference."],
    ["state/store.py", "SQLite: patterns, watchlist, key/value (Telegram offset). WAL for shared access."],
    ["alerts/*", "Telegram, Discord, composite fan-out, message formatter."],
    ["charts/chart.py", "Annotated candlestick PNG (bottoms, neckline, breakout) via mplfinance."],
    ["engine.py", "Orchestrates fetch -> detect -> persist -> confirm -> alert per ticker/timeframe."],
    ["run.py", "CLI entry for the daily scan; loads .env and config."],
    ["sync.py / listen.py", "Telegram watchlist control: one-shot poll and always-on long-poll listener."],
    ["watchlist.py", "Deterministic add/remove/list CLI (also used by hermes/qwen)."],
    ["backtest/*", "Walk-forward engine, metrics, parameter sweep, CLI."],
], col_widths=[5.2 * cm, 10.3 * cm])

h2("3.3 State and idempotency")
p("All state lives in one SQLite file. Detected patterns are stored with a stable "
  "<font face='Courier'>pattern_id</font> = hash(ticker, timeframe, bottom dates). Confirmation often "
  "arrives on a later run, so patterns persist between runs; an <font face='Courier'>alerted</font> flag "
  "guarantees each setup fires exactly once. This makes every scheduled run safe to repeat.")
story.append(PageBreak())

# ============================== 4. DETECTION ==================================
h1("4. The Detection Algorithm, Step by Step")
p("Given a frame of closed OHLCV bars for one ticker and timeframe:")
bullets([
    "<b>1. Swing lows:</b> mark every bar whose low is the minimum over +/- <font face='Courier'>swing_k</font> bars.",
    "<b>2. Candidate pairs:</b> for each pair of swing lows (B1 before B2), require their spacing to be "
    "within [min_bars_between, max_bars_between] and their lows within <font face='Courier'>bottom_tol_pct</font> of each other.",
    "<b>3. Neckline:</b> take the highest high strictly between the two bottoms; require its prominence "
    "above the bottoms to be at least <font face='Courier'>min_prominence_pct</font>.",
    "<b>4. Prior downtrend (optional):</b> require price to have declined into B1 &mdash; a reversal needs "
    "something to reverse.",
    "<b>5. Dedup:</b> cluster candidates whose necklines sit within ~2% and keep only the strongest "
    "(deepest, most symmetric), so one breakout is one setup, not many.",
    "<b>6. Persist:</b> store surviving structures as DETECTED (pending).",
    "<b>7. Confirm:</b> the first later closed candle that closes above neckline x (1 + buffer), is green, "
    "and carries volume >= factor x average -> CONFIRMED (alert). A close below the lower bottom, or "
    "expiry after max_bars_between, invalidates the pending pattern.",
])
image("detection_real.png", "Figure 2. A real double bottom the bot detected on AAPL (daily). The two "
      "blue markers are the bottoms, the dashed orange line is the neckline, and the green line marks "
      "the confirming bullish breakout candle. This is the exact chart image attached to the alert.")
h2("4.1 Tunable thresholds (config/config.yaml)")
table([
    ["Parameter", "Default", "Meaning"],
    ["lookback_bars", "90", "Detection window scanned per ticker."],
    ["swing_k", "3", "Bars each side required to qualify a swing point."],
    ["bottom_tol_pct", "0.03", "Max relative gap between the two bottom lows (3%)."],
    ["min_prominence_pct", "0.05", "Neckline must sit >= 5% above the bottoms."],
    ["min_bars_between", "5", "Bottoms not too close."],
    ["max_bars_between", "50", "Bottoms not too far; also pending-pattern expiry."],
    ["neckline_buffer_pct", "0.001", "Breakout must clear the neckline by 0.1% (noise guard)."],
    ["require_prior_downtrend", "true", "Require a decline into Bottom 1."],
    ["require_volume_confirmation", "true", "Enforce the breakout volume gate."],
    ["volume_avg_window", "20", "Bars used for the average-volume baseline."],
    ["volume_factor", "1.0", "Breakout volume >= this x average (raise ~1.5 for stricter)."],
], col_widths=[5.0 * cm, 2.2 * cm, 8.3 * cm])
p("A note on tooling: chart patterns like the double bottom are <b>not</b> provided by TA-Lib or "
  "pandas-ta (those cover indicators and single-candle patterns). The structural detection here is "
  "custom logic built on NumPy/pandas.")
story.append(PageBreak())

# ============================== 5. DELIVERY ===================================
h1("5. Alerting, Charts, Interaction &amp; Scheduling")

h2("5.1 Alerts and charts")
p("On confirmation the bot renders an annotated candlestick chart (mplfinance): the two bottoms marked, "
  "the neckline drawn, and the green breakout candle highlighted, with a volume panel. A composite "
  "alerter fans the message + chart out to Telegram (sendPhoto) and Discord (webhook file upload); a "
  "failure on one channel never blocks the other. Each alert includes the neckline, both bottoms, the "
  "breakout close, and a suggested stop reference below the bottoms.")

h2("5.2 Interactive watchlist (Telegram)")
p("The watchlist lives in SQLite and is editable from Telegram via a fixed two-button keyboard "
  "([+ Add] / [- Remove]) and the commands /list, /add SYMBOL, /remove SYMBOL. New symbols are "
  "validated against Yahoo before being added, and only the owner's chat id is honored. Because Telegram "
  "cannot wake a stopped program, an <b>always-on long-polling listener</b> (kept alive by launchd, "
  "auto-restart on crash and boot) provides instant responses. A one-shot polling variant also exists "
  "for cron-based operation; only one may poll a bot token at a time.")

h2("5.3 Scheduling (hermes) and a macOS gotcha")
p("The daily scan is a one-shot invoked by the hermes cron scheduler at 17:00 local time (Malaysia). "
  "Because the bot only acts on closed bars, exact timing is not critical. One practical lesson learned: "
  "macOS privacy protection (TCC) blocks launchd agents from executing shell scripts located in "
  "~/Desktop; the fix is to have launchd run the Python interpreter directly (mirroring an existing "
  "working service) rather than a wrapper script.")
story.append(PageBreak())

# ============================== 6. BACKTESTING ================================
h1("6. Backtesting &amp; Tuning")

h2("6.1 Methodology")
p("The backtester replays history through the <b>exact same</b> detect() and check_confirmation() code "
  "the live bot uses, walking forward bar by bar so there is no look-ahead. The first bar a pattern "
  "confirms is the entry. Each trade is then simulated forward:")
bullets([
    "<b>Entry:</b> the breakout candle's close.",
    "<b>Stop:</b> just below the lower of the two bottoms; risk = entry - stop.",
    "<b>Target (default):</b> the 'measured move' &mdash; neckline + (neckline - stop), i.e. the pattern "
    "height projected up. (A fixed reward:risk target is also available.)",
    "<b>Exit:</b> whichever of stop or target is hit first (stop assumed first if both hit in one bar, "
    "conservative), else a time-exit after max_hold_bars.",
])
p("Results are reported in R and aggregated into win rate, expectancy, total R, profit factor, and max "
  "drawdown, per ticker and overall. Caveats: the model ignores slippage, commissions and dividends, "
  "assumes one position per signal, and applies no position sizing &mdash; results are indicative, not "
  "guarantees.")
image("trade.png", "Figure 3. One backtested AAPL trade: entry at the breakout close, stop below the "
      "bottoms, and the measured-move target. The star marks the exit; the result is recorded in R "
      "(reward relative to the risk taken).")

h2("6.2 Measured results (Magnificent 7)")
table([
    ["Timeframe", "Period", "Trades", "Win %", "Profit factor", "Expectancy"],
    ["Daily", "2022-2026 (~4y)", "157", "68%", "1.27", "+0.08 R"],
    ["Weekly", "2015-2026 (~11y)", "69", "70%", "1.47", "+0.13 R"],
], col_widths=[2.6 * cm, 4.0 * cm, 2.0 * cm, 1.8 * cm, 2.9 * cm, 2.2 * cm])
p("A real but modest positive edge, with the weekly timeframe cleaner than daily &mdash; consistent with "
  "the principle that higher timeframes carry less noise.")
image("equity.png", "Figure 4. Cumulative-R equity curve across the Mag7 daily backtest (trades in "
      "chronological order). The shaded band is drawdown &mdash; how far the running total sits below "
      "its prior peak.")

h2("6.3 Parameter sweep with out-of-sample guard")
p("The sweep grid-searches detection thresholds, backtests each combination, and splits the trades into "
  "in-sample (older) and out-of-sample (newest 30%) by entry date. It ranks by an in-sample objective "
  "while displaying out-of-sample side by side, so overfit settings are exposed. Example daily result:")
table([
    ["volume_factor", "min_prominence", "IS profit factor", "OOS profit factor", "Verdict"],
    ["2.0", "0.08", "3.86", "0.71", "Overfit (OOS collapses)"],
    ["2.0", "0.05", "3.71", "3.01", "Holds out-of-sample"],
    ["1.5", "0.05", "1.50", "2.17", "Holds"],
    ["1.0", "0.05 (current)", "1.27", "1.28", "Stable, weakest edge"],
], col_widths=[2.7 * cm, 3.1 * cm, 3.1 * cm, 3.3 * cm, 3.3 * cm])
p("The lesson the tool teaches: the best in-sample number (2.0/0.08) is a trap, but a broad plateau "
  "(volume_factor 1.5-2.0 with min_prominence 0.05) improves the edge and survives out-of-sample. A "
  "sweep finds candidates; it does not prove an edge.")
image("sweep_heatmap.png", "Figure 5. Profit factor across a volume_factor x min_prominence grid, "
      "in-sample (left) vs out-of-sample (right); greener is better. The volume_factor=2.0 column looks "
      "superb in-sample, but the top cell (2.0 / 0.08) turns red out-of-sample &mdash; overfit. The "
      "settings that stay green in BOTH panels are the trustworthy ones.")
story.append(PageBreak())

# ============================== 7. TIMELINE ===================================
h1("7. Development Timeline")
p("The project was built incrementally, each step verified with tests and live runs before the next.")
table([
    ["Phase", "What was built"],
    ["1. MVP", "Daily double-bottom detect + confirm; Telegram + Discord alerts; SQLite state; idempotent daily run."],
    ["1b. Expansion", "Magnificent-7 watchlist; daily + weekly timeframes; annotated chart images in alerts."],
    ["Scheduling", "hermes cron for the daily scan; .env secret loading; timezone-correct timing."],
    ["1.5 Watchlist UX", "Watchlist moved into SQLite; Telegram commands + buttons; deterministic CLI for hermes/qwen."],
    ["Listener", "Always-on long-polling listener (launchd) for instant Telegram interaction."],
    ["Quality: dedup", "Per-neckline dedup: collapsed ~26 backlog alerts to ~14 (one per setup)."],
    ["Quality: volume", "Volume-confirmation gate on the breakout candle."],
    ["Backtesting", "Walk-forward engine + metrics + CLI; measured the edge on 4-11 years of history."],
    ["Parameter sweep", "Grid search with in-sample/out-of-sample validation to tune thresholds safely."],
    ["Documentation", "This design document."],
], col_widths=[3.4 * cm, 12.1 * cm])

# ============================== 8. RISKS ======================================
h1("8. Risks &amp; Limitations")
bullets([
    "<b>False positives are inherent</b> to pattern detection; the prominence, similarity, dedup and "
    "volume filters mitigate but never eliminate them.",
    "<b>Data quality:</b> yfinance is an unofficial, free feed with no SLA; it can be delayed, gap, or "
    "change. Prices are split/dividend-adjusted.",
    "<b>Modelling gaps:</b> the backtest ignores slippage, commissions, dividends and position sizing; "
    "live results will differ.",
    "<b>Overfitting risk</b> when tuning; always prefer settings that hold out-of-sample.",
    "<b>Not financial advice / not automated execution:</b> Quantus alerts; a human decides. Manual "
    "confirmation before trading is intentional, given the probabilistic nature of the signals.",
])

# ============================== 9. ROADMAP ====================================
h1("9. Roadmap")
bullets([
    "<b>Apply tuned thresholds</b> from the sweep (e.g. volume_factor 1.5) for higher-quality alerts.",
    "<b>Risk management &amp; position sizing:</b> convert R-multiples into dollar equity curves and a "
    "suggested size per alert (ATR or fixed-fractional).",
    "<b>More patterns:</b> inverse head-and-shoulders, triple bottom &mdash; reusing the swing/neckline "
    "machinery.",
    "<b>Multi-timeframe confirmation:</b> only alert a daily setup when a weekly setup aligns.",
    "<b>Fundamental overlay</b> and, much later, semi-/fully-automated execution with hard guardrails.",
])

spacer(10)
p("<i>Quantus &mdash; technical design document. Generated programmatically from "
  "docs/generate_pdf.py; regenerate to keep in sync with the codebase.</i>")


def build():
    doc = SimpleDocTemplate(
        OUT, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=1.8 * cm,
        title="Quantus Design Document", author="Quantus",
    )
    doc.build(story)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    build()
