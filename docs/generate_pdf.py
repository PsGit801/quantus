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
story.append(Paragraph("A Double-Bottom &ldquo;Flush-Reclaim&rdquo; Chart-Pattern Scanner &amp; Alert Bot", SUB))
story.append(Paragraph("Design, Backend Architecture &amp; Trading Concepts &mdash; explained from scratch", SUB))
story.append(Spacer(1, 1.2 * cm))
story.append(Paragraph("Technical Design Document &mdash; generated 2026-07-15", CENTER))
story.append(Spacer(1, 1.5 * cm))
story.append(Paragraph(
    "Quantus watches a list of stocks on the daily and weekly timeframes and looks for one specific "
    "chart setup: a <b>double-bottom &ldquo;flush-reclaim&rdquo;</b> (a bear trap). When it finds one, it sends "
    "you a message on Telegram and Discord &mdash; with a labelled price chart, a suggested entry, stop, "
    "and target, and a position size. It does <b>not</b> place trades; a human decides. This document "
    "explains what all of that means, starting from &ldquo;what is a candlestick,&rdquo; so a reader new to "
    "trading and charts can follow the whole design.", BODY))
story.append(Spacer(1, 0.6 * cm))
story.append(Paragraph(
    "<i>Nothing here is financial advice. Quantus is a personal research and alerting tool.</i>", CENTER))
story.append(PageBreak())

# ============================== 1. OVERVIEW ===================================
h1("1. What Quantus Is (in plain terms)")
p("Quantus is a personal, single-user program that <b>scans stock charts and alerts you</b> when a "
  "particular bullish reversal setup appears. Think of it as a tireless assistant that watches your "
  "watchlist every day and taps you on the shoulder &mdash; with a chart and the key numbers &mdash; "
  "when something worth a look shows up. You still make every trading decision yourself.")
h2("At a glance")
bullets([
    "<b>Data:</b> free end-of-day price history from Yahoo Finance (via the <font face='Courier'>yfinance</font> library). No paid data feed.",
    "<b>Watchlist:</b> ~23 higher-volatility stocks (e.g. PLTR, COIN, RIVN, HOOD, FOXA), stored in a small database and editable live from Telegram. Volatile names are used because the setup depends on sharp sell-offs, which calm large-caps rarely produce.",
    "<b>Timeframes:</b> daily and weekly, scanned separately (a weekly signal is rarer and stronger).",
    "<b>The setup:</b> a double-bottom <i>flush-reclaim</i> &mdash; explained step by step in Sections 2&ndash;5.",
    "<b>Each alert carries:</b> a labelled candlestick chart, the entry / stop / target, the reward-to-risk ratio, and a suggested position size.",
    "<b>Scheduling:</b> a once-a-day scan run automatically; plus an always-on helper so the Telegram buttons respond instantly.",
    "<b>Honesty built in:</b> a backtester and a parameter sweep measure whether the idea actually works on history, with an out-of-sample check that guards against fooling ourselves.",
])
p("The code is Python 3.11 (the <font face='Courier'>ddbot</font> package) with 85 automated tests. Every "
  "part sits behind a clean interface (data source, alerter, pattern, store) so pieces can be swapped "
  "without rewrites. <b>Important framing:</b> as the backtesting section shows, this strategy does not "
  "yet have a <i>proven</i> mechanical edge &mdash; so Quantus is used as a <b>discretionary finder</b> "
  "(it finds candidates; you judge each chart), not an auto-trader.")

# ============================== 2. CHARTS 101 =================================
h1("2. Charts 101: How to Read the Pictures")
p("Everything Quantus does is built on the <b>candlestick chart</b>. If you already read charts, skim "
  "this; if not, this section gives you the whole vocabulary the rest of the document uses.")

h2("2.1 What a candlestick is")
p("Each candlestick summarises the price action for one period of time (one day on the daily chart, one "
  "week on the weekly). It records four prices: the <b>open</b> (first trade of the period), the "
  "<b>high</b> (highest price reached), the <b>low</b> (lowest), and the <b>close</b> (last trade). The "
  "thick part is the <b>body</b> (open&ndash;to&ndash;close); the thin lines above and below are the "
  "<b>wicks</b> (also called shadows or tails), reaching to the high and the low. By convention the "
  "candle is <b>green</b> when price closed higher than it opened (buyers won the period) and <b>red</b> "
  "when it closed lower (sellers won).")
image("candles.png", "Figure 1. A candlestick records four prices (open, high, low, close). The body is "
      "open-to-close; the wicks reach to the high and low. Four shapes matter for this strategy: a full "
      "green bar (closes near its high), a bullish hammer (long lower wick = buyers rejected lower "
      "prices), a long-upper-wick bar (a rally that got sold off before the close &mdash; NOT a clean "
      "entry here), and a red bar.")
p("<b>Why the wicks matter so much here:</b> a long <b>upper</b> wick means price pushed up during the "
  "period but was <b>sold back down</b> before the close &mdash; a sign of sellers overhead. A long "
  "<b>lower</b> wick (a &ldquo;hammer&rdquo; or &ldquo;pin bar&rdquo;) means price dropped but buyers "
  "<b>rejected</b> the lower prices and pushed the close back up &mdash; a bullish sign. Quantus only "
  "treats a candle as a valid entry trigger if it is a clean bullish shape (a full green body or a "
  "hammer) with a <i>small</i> upper wick.")

h2("2.2 Support, resistance, and trend")
p("<b>Support</b> is a price level where buyers have repeatedly stepped in and stopped a decline (a "
  "&ldquo;floor&rdquo;). <b>Resistance</b> is the mirror image: a level where sellers repeatedly cap a "
  "rally (a &ldquo;ceiling&rdquo;). A <b>trend</b> is the general direction &mdash; a downtrend is a "
  "series of lower lows. These three words are all we need: the strategy is about price falling into a "
  "support area, being pushed below it in a trap, and then reversing.")

# ============================== 3. CONCEPTS ===================================
h1("3. The Strategy&rsquo;s Ideas, One at a Time")

h2("3.1 The double bottom and the neckline")
p("A <b>double bottom</b> is a bullish reversal shaped like the letter &ldquo;W.&rdquo; After a decline, "
  "price makes a low (<b>Bottom 1</b>), bounces up to an interim <b>peak</b>, falls again toward the "
  "same area, and eventually turns back up. The two bottoms mark a support level that buyers defended. "
  "The interim peak is the <b>neckline</b> &mdash; the resistance ceiling between the bottoms. In the "
  "classic version, you buy when price breaks <i>above</i> the neckline. Quantus uses a sharper "
  "variation, below.")

h2("3.2 The flush-reclaim (a &ldquo;bear trap&rdquo;) &mdash; the actual entry")
p("Instead of waiting for a breakout above the neckline, Quantus enters <b>below</b> the neckline, on a "
  "failed breakdown. The sequence:")
bullets([
    "Price falls into <b>Bottom 1</b> after a prior decline (there must be a downtrend to reverse).",
    "It <b>recovers</b> up toward an interim peak &mdash; that peak becomes the <b>neckline</b> / target.",
    "Then comes a <b>steep, high-volume flush</b>: a near-vertical sell-off that <b>undercuts</b> Bottom 1 "
    "(pokes below the old floor). This is the <b>bear trap</b> &mdash; it looks like a fresh breakdown and "
    "flushes out nervous sellers.",
    "Within a few bars a <b>clean bullish candle reclaims</b> back above Bottom 1&rsquo;s low (but still "
    "below the neckline). That failed breakdown is the signal: sellers had their chance and could not "
    "hold the lows. <b>That reclaim candle&rsquo;s close is the entry.</b>",
])
p("The appeal is buying the reversal <b>cheaply</b> (well below the neckline) right as the trap springs, "
  "rather than chasing a breakout. The risk is that the &ldquo;trap&rdquo; is a real breakdown &mdash; "
  "which is what the stop is for.")
image("anatomy.png", "Figure 2. The flush-reclaim. Price declines to Bottom 1, recovers to the neckline, "
      "then a steep high-volume flush undercuts Bottom 1 (the bear trap). A clean bullish candle reclaims "
      "back above Bottom 1 = the entry, below the neckline. The stop sits below the flush; the target is a "
      "&lsquo;measured move&rsquo; above the neckline.")

h2("3.3 Finding it objectively: swing points and prominence")
p("To turn this picture into code, the bottoms are found as <b>swing lows</b>: a bar is a swing low if "
  "its low is the lowest within a symmetric window of <font face='Courier'>swing_k</font> bars on each "
  "side. <b>Prominence</b> then measures how far the neckline sits above the bottom, as a percentage; "
  "requiring a minimum (5%) throws away shallow, sideways noise and keeps setups with real depth.")

h2("3.4 Measuring &ldquo;steep&rdquo; and &ldquo;capitulation&rdquo;: ATR and volume")
p("Two things make the flush a genuine trap rather than a gentle dip. First, <b>steepness</b>, measured "
  "with the <b>ATR</b> (Average True Range) &mdash; a standard gauge of how much a stock typically moves "
  "per bar (its volatility). Requiring the drop from the peak to be at least a multiple of ATR (e.g. "
  "3&times;) means &ldquo;much bigger than a normal move&rdquo; &mdash; a near-vertical plunge. Second, "
  "<b>volume</b>: the flush bar must trade well above its recent average volume, the fingerprint of "
  "panic selling (<b>capitulation</b>).")

h2("3.5 The clean reclaim bar (why the candle shape matters)")
p("The entry candle must be a <b>clean bullish shape</b> so we are not buying a half-hearted bounce. It "
  "must be green and either (a) a <b>full body</b> that closes near its high, or (b) a <b>hammer</b> with "
  "a long lower wick &mdash; and in both cases the <b>upper wick must be small</b> (the close lands in "
  "the top 15% of the bar&rsquo;s range). A green candle that rallied but got <b>sold off</b> into the "
  "close leaves a long upper wick; Quantus rejects it, because that overhead selling is exactly what a "
  "reversal entry does not want.")

h2("3.6 Only closed bars (no &ldquo;repainting&rdquo;)")
p("Quantus acts only on <b>completed</b> candles; the still-forming current bar is ignored, because it "
  "can change (&ldquo;repaint&rdquo;) before it closes. This discipline is what makes a backtest honest: "
  "the bot never reacts to information that did not fully exist yet.")

h2("3.7 Keeping score: R-multiples, expectancy, profit factor, drawdown")
bullets([
    "<b>R (one unit of risk):</b> the distance from your entry to your stop. If a trade makes twice what "
    "it risked, that is +2R; hitting the stop is -1R. Measuring in R lets you compare trades across "
    "different stocks and sizes.",
    "<b>Expectancy (average R):</b> the mean R per trade &mdash; your average result per signal. Positive "
    "expectancy is the definition of an edge.",
    "<b>Win rate:</b> the share of trades that make money. A high win rate with tiny average R is not "
    "automatically good; the two must be read together.",
    "<b>Profit factor:</b> total winning R divided by total losing R. Above 1.0 is profitable; ~2+ is strong.",
    "<b>Max drawdown:</b> the deepest peak-to-trough dip of the running total &mdash; the worst stretch "
    "you would have had to sit through.",
])

h2("3.8 Not fooling ourselves: walk-forward and out-of-sample")
p("<b>Overfitting</b> is tuning a strategy until it looks perfect on the past, then watching it fail "
  "live. Two defenses are built in. <b>Walk-forward</b> testing replays history bar by bar, only ever "
  "using data that existed at each moment. <b>Out-of-sample</b> testing hides the most recent slice of "
  "history, tunes on the older part, and then checks whether the choice still works on the hidden slice. "
  "If an edge vanishes out-of-sample, it was a mirage and is thrown away. (This exact check is what told "
  "us the original exit rule did not work &mdash; see Section 7.)")
story.append(PageBreak())

# ============================== 4. ARCHITECTURE ===============================
h1("4. Backend Architecture")
p("The system is a set of small, single-purpose modules connected in a straight line. The <b>same</b> "
  "detection code powers both the live scanner and the backtester, so what we measure is what we trade.")

h2("4.1 Data-flow pipeline (the daily scan)")
code(
    "scheduled daily scan\n"
    "      |\n"
    "      v\n"
    "  ddbot.run  ->  YahooDataProvider          (fetch completed OHLCV bars)\n"
    "      |            |\n"
    "      |            v\n"
    "      |         detect()                     (swing lows -> recovery/neckline ->\n"
    "      |            |                          steep undercut flush = candidate)\n"
    "      |            v\n"
    "      |         dedupe_by_neckline()         (one setup per resistance level)\n"
    "      |            |\n"
    "      |            v\n"
    "      |         PatternStore (SQLite)        (remember pending setups between runs)\n"
    "      |            |\n"
    "      |            v\n"
    "      |         check_confirmation()         (clean reclaim below neckline? -> set\n"
    "      |            |                          entry + ATR stop + measured target)\n"
    "      |            v\n"
    "      |         multi-timeframe gate -> chart -> Telegram + Discord\n"
    "      v\n"
    "   exit (idempotent: each confirmed setup is alerted exactly once)"
)

h2("4.2 Module map")
table([
    ["Module", "Responsibility"],
    ["data/yahoo.py", "Fetch price history from Yahoo; drop the still-forming bar; validate symbols."],
    ["patterns/swings.py", "Swing-low / swing-high (fractal) detection."],
    ["patterns/double_bottom.py", "detect(); dedupe_by_neckline(); check_confirmation(); compute_stop()/compute_target()."],
    ["patterns/base.py", "The DoubleBottom record (entry, stop, target), states, stable id."],
    ["state/store.py", "SQLite: setups (incl. stop/target), watchlist, key/value. Migrates old DBs."],
    ["risk.py", "Position sizing: how many shares to risk a fixed % of the account."],
    ["mtf.py", "Multi-timeframe filter (only take a daily signal if the weekly trend agrees)."],
    ["alerts/*", "Telegram, Discord, fan-out, and the message formatter."],
    ["charts/chart.py", "The labelled candlestick PNG attached to each alert (mplfinance)."],
    ["engine.py", "Runs fetch -> detect -> remember -> confirm -> alert per ticker/timeframe."],
    ["journal.py", "Replays past alerts against later prices to score how they actually did."],
    ["backtest/*", "Walk-forward engine, metrics, parameter sweep, CLI."],
], col_widths=[5.2 * cm, 10.3 * cm])

h2("4.3 Memory and &ldquo;idempotency&rdquo;")
p("All state lives in one SQLite file. Each setup gets a stable id (a hash of the ticker, timeframe, and "
  "the two bottom dates). Because a setup often confirms on a <i>later</i> day, setups persist between "
  "runs; an <font face='Courier'>alerted</font> flag guarantees each one fires <b>exactly once</b>. That "
  "makes every scheduled run safe to repeat &mdash; &ldquo;idempotent.&rdquo; When the exit model was "
  "added, the database automatically gained two new columns (the stop and target prices) via a small "
  "migration, so existing data keeps working.")
story.append(PageBreak())

# ============================== 5. DETECTION ==================================
h1("5. The Detection Algorithm, Step by Step")
p("Given a set of completed price bars for one ticker and timeframe:")
bullets([
    "<b>1. First bottom (B1):</b> find a swing low, and require a <b>prior downtrend</b> into it.",
    "<b>2. Recovery / neckline:</b> require a bounce to an interim peak at least "
    "<font face='Courier'>min_prominence_pct</font> above B1. That peak is the neckline (and the target).",
    "<b>3. Steep flush (B2):</b> a near-vertical drop that <b>undercuts B1&rsquo;s low</b> within "
    "<font face='Courier'>flush_max_bars</font>, where the fall is at least "
    "<font face='Courier'>flush_atr_mult</font>&times;ATR <b>and</b> the flush bar&rsquo;s volume is well "
    "above its recent average (capitulation).",
    "<b>4. Dedup:</b> collapse near-identical necklines so one trap is one setup.",
    "<b>5. Remember:</b> store the surviving structures as pending.",
    "<b>6. Reclaim = entry:</b> within <font face='Courier'>reclaim_window</font> bars, the first "
    "<b>clean bullish candle</b> (full green or hammer, small upper wick) that closes above B1&rsquo;s "
    "low but below the neckline confirms the setup. The entry is that close; the <b>stop</b> and "
    "<b>target</b> are computed here (Section 3.4&ndash;3.5 and 7).",
    "<b>Invalidation:</b> a close back below the flush low, a reclaim that overshoots above the neckline "
    "(that&rsquo;s a plain breakout, not our below-neckline entry), or the reclaim window elapsing.",
])
image("detection_real.png", "Figure 3. A real flush-reclaim Quantus detected (FOXA, weekly). The blue "
      "markers are the two bottoms (the second undercutting the first), the dashed orange line is the "
      "neckline, and the star marks the confirming reclaim candle. This is the exact image attached to "
      "the alert.")
h2("5.1 Tunable thresholds (config/config.yaml)")
p("Everything is a named knob in one config file, so the strategy can be tuned without touching code.")
table([
    ["Parameter", "Default", "Meaning"],
    ["lookback_bars", "90", "How many recent bars are scanned per ticker."],
    ["swing_k", "3", "Bars each side needed to qualify a swing low."],
    ["min_prominence_pct", "0.05", "Neckline must sit >= 5% above Bottom 1 (real depth)."],
    ["max_bars_between", "50", "Max bars from Bottom 1 to the flush."],
    ["require_undercut", "true", "The flush must poke BELOW Bottom 1's low (the trap)."],
    ["flush_atr_mult", "3.0", "Peak->flush drop must be >= 3x ATR (a near-vertical plunge)."],
    ["flush_atr_window", "14", "Bars used to measure ATR (typical move size)."],
    ["flush_max_bars", "3", "The flush must happen within this many bars."],
    ["flush_volume_factor", "1.5", "Flush-bar volume >= 1.5x its recent average (capitulation)."],
    ["reclaim_window", "4", "The reclaim must occur within this many bars of the flush."],
    ["reclaim_min_body_frac", "0.60", "Full green bar: body >= 60% of the bar's range."],
    ["reclaim_max_upper_wick_frac", "0.15", "Upper wick <= 15% of range (no 'long head')."],
    ["reclaim_min_lower_wick_frac", "0.50", "Hammer: lower wick >= 50% of range."],
    ["stop_mode / stop_atr_mult", "atr / 3.5", "Stop = entry - 3.5x ATR (see Section 7)."],
    ["target_mode", "measured_move", "Target = neckline + (neckline - stop)."],
], col_widths=[5.6 * cm, 2.6 * cm, 7.3 * cm])
p("A note on tooling: multi-bar chart patterns like this are <b>not</b> provided by off-the-shelf "
  "libraries such as TA-Lib (which cover indicators and single-candle patterns). The structural "
  "detection here is custom logic built on NumPy and pandas.")
story.append(PageBreak())

# ============================== 6. DELIVERY ===================================
h1("6. Alerts, Charts, Interaction &amp; Scheduling")

h2("6.1 What an alert looks like")
p("On confirmation the bot renders a labelled candlestick chart (the two bottoms, the neckline, and the "
  "reclaim candle marked) and sends it, with the message, to Telegram and Discord at once; a failure on "
  "one channel never blocks the other. The message states the entry (reclaim close), the neckline, the "
  "<b>target</b> and <b>stop</b>, the <b>reward-to-risk</b> ratio, and a <b>suggested position size</b> "
  "(how many shares to risk a fixed 1% of a configured account). A footnote reminds you it is a "
  "discretionary setup to review by eye.")

h2("6.2 Multi-timeframe agreement")
p("A daily signal is stronger when the bigger picture agrees. With the multi-timeframe filter on, a "
  "<b>daily</b> alert only fires if the <b>weekly</b> trend is up (weekly close above its moving "
  "average). Weekly signals are not gated &mdash; they are the higher timeframe.")

h2("6.3 Editing the watchlist from Telegram")
p("The watchlist lives in the database and is editable from your phone via two buttons "
  "([+ Add] / [- Remove]) and the commands /list, /add SYMBOL, /remove SYMBOL. New symbols are checked "
  "against Yahoo before being added, and only your own chat is allowed to make changes. Because Telegram "
  "cannot wake a stopped program, a small always-on listener (auto-restarting) makes the buttons respond "
  "instantly.")

h2("6.4 Scheduling and a macOS lesson")
p("The daily scan runs once a day, automatically. Because the bot only acts on completed bars, the exact "
  "minute does not matter. One practical lesson: macOS privacy protection blocks scheduled agents from "
  "running scripts kept in the Desktop folder; the fix was to move the project out of Desktop and run "
  "the Python interpreter directly.")
story.append(PageBreak())

# ============================== 7. BACKTESTING ================================
h1("7. Does It Actually Work? Backtesting &amp; the Exit Study")

h2("7.1 How the backtest works")
p("The backtester replays history through the <b>exact same</b> detection code the live bot uses, "
  "walking forward bar by bar so it never peeks at the future. The first bar a setup reclaims is the "
  "entry; the trade is then followed until it hits its stop (a loss) or its target (a win), or times "
  "out. Every result is recorded in R (Section 3.7). Caveats: the model ignores trading costs, slippage, "
  "and dividends, and takes one position per signal &mdash; so results are indicative, not a promise.")
image("trade.png", "Figure 4. One backtested trade. Entry at the reclaim close, an ATR-based stop below, "
      "and a measured-move target above; the star marks the exit. The outcome is recorded in R (reward "
      "relative to the risk taken).")

h2("7.2 The key finding: the exit was the problem")
p("The first version of the strategy stopped out just below the deep flush and aimed only at the "
  "neckline. Backtesting showed the entry was fine (~60% of trades were winners) but the strategy still "
  "<b>lost money out-of-sample</b>: the stop was so far away that the few losses outweighed the many "
  "small wins. So a dedicated <b>exit-model study</b> swept different stop and target rules across ~36 "
  "volatile stocks over ~8 years, splitting every result into in-sample and out-of-sample.")
table([
    ["Stop &rarr; Target", "In-sample", "Out-of-sample", "Verdict"],
    ["ATR (3.5x) &rarr; measured move", "+0.62 R,  PF 2.8", "+0.71 R,  PF 4.5", "Holds out-of-sample"],
    ["ATR (3.5x) &rarr; 2R target", "+0.53 R,  PF 2.4", "+0.87 R,  PF 5.3", "Holds out-of-sample"],
    ["Flush low &rarr; neckline (original)", "+0.04 R,  PF 1.1", "-0.19 R,  PF 0.6", "Fails (negative OOS)"],
    ["Reclaim-bar low (tight) &rarr; any", "negative", "negative", "Worst (whipsawed out)"],
], col_widths=[6.4 * cm, 3.3 * cm, 3.3 * cm, 2.5 * cm])
p("The lesson: a <b>wider, volatility-scaled ATR stop</b> (giving the trade room) with a <b>measured-move "
  "target</b> turns a losing exit into one that stays profitable out-of-sample &mdash; positive with a "
  "profit factor above 2 in <i>both</i> samples, the signature of a real (not curve-fit) effect. A very "
  "tight stop was the worst: it got shaken out by normal wobble. That ATR/measured-move exit is now the "
  "live default. <b>Honest caveat:</b> the setup is rare, so this rests on only ~16 out-of-sample trades "
  "&mdash; promising, not proof. That is exactly why Quantus stays a discretionary finder.")
image("exit_study.png", "Figure 5. Profit factor for every stop-model (rows) x target-model (columns) "
      "combination, in-sample (left) vs out-of-sample (right); greener is better. The ATR-stop rows stay "
      "green in both panels; the tight reclaim-bar stop is red; the original flush-low/neckline corner "
      "fades. Only settings green in BOTH panels are trustworthy.")
image("equity.png", "Figure 6. The running total (in R) of the backtested trades across the volatile "
      "universe, in date order. The shaded band is drawdown &mdash; how far below its prior peak the "
      "running total sat at each point.")
story.append(PageBreak())

# ============================== 8. TIMELINE ===================================
h1("8. How the Project Evolved")
p("Quantus was built and revised incrementally, each step verified with tests and live runs. The most "
  "important changes were driven by evidence, not opinion.")
table([
    ["Stage", "What changed"],
    ["MVP", "Daily double-bottom detect + confirm; Telegram + Discord alerts; SQLite memory; idempotent daily run."],
    ["Expansion", "Weekly timeframe; labelled chart images; automatic scheduling; watchlist in the database."],
    ["Telegram control", "Buttons + commands to edit the watchlist; an always-on listener for instant replies."],
    ["Quality filters", "One-alert-per-setup dedup; volume confirmation; multi-timeframe agreement."],
    ["Backtesting", "Walk-forward engine, metrics, and a parameter sweep with an out-of-sample guard."],
    ["Risk + journal", "Suggested position size on every alert; a journal that scores how past alerts played out."],
    ["Strategy pivot", "Replaced the breakout entry with the flush-reclaim (bear-trap) entry below the neckline."],
    ["Cleaner entries", "Required the reclaim candle to be a clean bullish shape (full green / hammer, small upper wick)."],
    ["Exit-model study", "Found the flush-low/neckline exit was negative out-of-sample; adopted an ATR stop + measured-move target that holds up."],
    ["Digest + health", "Weekly digest of live results, pushed to Telegram/Discord; scan/listener heartbeats warn on silent failure."],
    ["This document", "Rewritten to explain the current strategy from scratch."],
], col_widths=[3.6 * cm, 11.9 * cm])

# ============================== 9. RISKS ======================================
h1("9. Risks &amp; Limitations")
bullets([
    "<b>No <i>proven</i> mechanical edge yet.</b> The improved exit looks good but rests on a small "
    "out-of-sample sample. Treat every alert as a candidate to review, not a signal to trade blindly.",
    "<b>False positives are inherent</b> to pattern detection; the prominence, steep-flush, volume and "
    "clean-reclaim filters reduce them but never eliminate them.",
    "<b>Data quality:</b> Yahoo Finance is a free, unofficial feed with no guarantees; it can be delayed, "
    "gap, or be revised. Prices are split/dividend-adjusted.",
    "<b>Modelling gaps:</b> the backtest ignores trading costs, slippage and dividends, and uses one "
    "position per signal &mdash; live results will differ.",
    "<b>Overfitting risk</b> whenever thresholds are tuned; always prefer settings that survive "
    "out-of-sample.",
    "<b>Not financial advice, and not automated:</b> Quantus alerts; a human decides and executes.",
])

# ============================== 10. ROADMAP ===================================
h1("10. Roadmap")
bullets([
    "<b>Validate live:</b> let the journal accumulate real forward signals under the new exit and confirm "
    "the edge holds outside the backtest &mdash; the single most valuable next step.",
    "<b>More patterns:</b> inverse head-and-shoulders, triple bottom &mdash; reusing the swing/neckline "
    "machinery.",
    "<b>Observability (in place):</b> a weekly digest of live results plus scan/listener heartbeats now "
    "ship; extend with a small dashboard and longer-horizon reporting.",
    "<b>Later:</b> a fundamental overlay, and &mdash; only with hard guardrails &mdash; semi-automated execution.",
])

spacer(10)
p("<i>Quantus &mdash; technical design document. Generated programmatically from "
  "docs/generate_pdf.py; regenerate to keep it in sync with the codebase.</i>")


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
