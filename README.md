# ddbot — Double-Bottom (Flush-Reclaim) Detection & Alert Bot

Pulls OHLCV for a watchlist on **daily and weekly** timeframes, detects a **double-bottom
flush-reclaim** (bear-trap) setup, and alerts to **Telegram + Discord** with an **annotated
candlestick chart** showing the two bottoms, the neckline, and the reclaim (entry) bar.

Unlike a classic breakout entry, the entry here is **below the neckline**: a steep capitulation
flush undercuts the first bottom (a bear trap), then a clean bullish candle reclaims back above it —
you buy the reversal cheaply, with the stop just under the flush low and the neckline as the target.

Each timeframe is scanned independently and fires its own alert (weekly is a stronger, rarer signal).

> **Discretionary tool, not a mechanical edge.** Backtesting (see below) shows the setup is strongly
> positive in-sample but **breaks even out-of-sample** at every threshold — no robust *mechanical*
> edge was found. The bot is used to *find* clean flush-reclaims for a human to judge on the chart,
> not to trade automatically. Every alert says so.

## How it works

```
hermes cron ──> python -m ddbot.run ──> yfinance ──> detect ──> SQLite state ──> confirm ──> alert
```

Each run is self-contained and **idempotent**: pending patterns are persisted to SQLite, so a
confirmation that arrives days later is caught, and a confirmed setup is never alerted twice. Only
**closed** bars are ever acted on (the current-day daily bar repaints, so it is dropped by default).

### Detection logic (`src/ddbot/patterns/double_bottom.py`)

The structure (`detect`), then the entry trigger (`check_confirmation`) — both on **closed bars only**:

1. **First bottom (B1)** — a swing low (low is the min over ±`swing_k` bars), with a **prior
   downtrend** into it (a reversal needs something to reverse).
2. **Recovery to the neckline** — price rebounds to an interim peak at least `min_prominence_pct`
   above B1. That peak is the **neckline** (the target).
3. **Steep flush (B2)** — a sharp capitulation leg that **undercuts B1's low** (`require_undercut`)
   within `flush_max_bars` bars, where the drop is at least `flush_atr_mult × ATR(flush_atr_window)`
   (steepness) **and** the flush bar's volume is ≥ `flush_volume_factor` × its `flush_volume_window`
   average (capitulation). This bear trap is the whole point.
4. **Reclaim = entry** — within `reclaim_window` bars after the flush, the first bar that reclaims
   back **above B1's low but still below the neckline**, *and* is a **clean bullish candle**
   (see below). Entry = that close; stop = flush low; target = neckline.
5. **Invalidation** — a close back **below the flush low** (the trap deepened), a reclaim that
   **overshoots the neckline** (that's a straight breakout, not a below-neckline entry), or the
   reclaim window elapsing with no clean bar.
6. **Dedup** — candidates whose necklines sit within ~2% are collapsed to the strongest, so one
   setup = one alert.

**Clean reclaim bar (step 4).** The entry candle must be one of two clean bullish shapes — both with
a **small upper wick** (no "long head"): a **full green body** (`body ≥ reclaim_min_body_frac` of the
bar's range) *or* a **bullish pin bar / hammer** (`lower_wick ≥ reclaim_min_lower_wick_frac`), with
`upper_wick ≤ reclaim_max_upper_wick_frac` in both cases. A green body is required. This rejects
indecisive or long-wicked bars so entries fire only on a decisive reclaim.

All thresholds live in `config/config.yaml`.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env      # fill in Telegram token/chat_id and/or Discord webhook
```

## Run

```bash
python -m ddbot.run --dry-run -v      # print alerts instead of sending (safe to try now)
python -m ddbot.run                   # send to configured channels
```

hermes should invoke `python -m ddbot.run` once daily, after the US close.

## Test

```bash
pytest
```

Covers swing detection, the steep-undercut flush structure, near-misses (no undercut, not steep
enough, no volume spike), reclaim confirmation and the clean-bar rule (full green / hammer accept;
long-upper-wick and weak bars reject), the invalidation paths (deeper flush, neckline overshoot,
elapsed window), and the end-to-end idempotency guarantee.

## Alerts

`Telegram + Discord` fire together via a composite alerter, each with the chart PNG attached
(Telegram `sendPhoto`, Discord webhook file upload). A failure on one channel is logged and does not
block the other. Configure either or both via `.env`. If none are configured, alerts are logged as
dropped. `--dry-run` prints the message and writes the chart under `charts/` (path printed) so you
can preview without sending.

## Manage the watchlist

The watchlist lives in the SQLite `watchlist` table (seeded once from `config.yaml`'s `tickers`). The
daily scanner reads it, so edits take effect on the next scan. There are two ways to edit it.

### 1. CLI / hermes + qwen (recommended)

A deterministic CLI does all mutations (symbols validated against Yahoo before adding):

```bash
./scripts/watchlist.sh list
./scripts/watchlist.sh add PLTR COIN
./scripts/watchlist.sh remove TSLA
```

Because it's a plain command, your hermes local LLM (qwen) can drive it from natural language — tell
hermes *"add Palantir and Coinbase to the ddbot watchlist"* and it runs `scripts/watchlist.sh add …`.
The LLM handles the language; the CLI does the safe, structured update. No polling, no daemon.

### 2. Telegram, live (for mobile)

An always-on listener (`ddbot.listen`) long-polls Telegram so the ➕/➖ buttons and `/add` `/remove`
`/list` commands respond **instantly**. Only your `TELEGRAM_CHAT_ID` is honored.

Install it as a launchd service (auto-starts on login, restarts on crash):

```bash
cp deploy/ai.ddbot.telegram-listener.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/ai.ddbot.telegram-listener.plist
launchctl list | grep ddbot      # confirm it's running
```

Or run it manually to test: `./scripts/listen.sh`

**Important:** only one process may poll a bot token. If you previously scheduled the
`ddbot-watchlist-sync` cron, **delete it** — running it alongside the listener causes Telegram
"Conflict" errors. (`ddbot.sync` remains for one-shot/cron use if you ever prefer that over the
listener; don't run both.)

## Backtesting

Measure the strategy's edge by replaying history through the **exact live detector** (walk-forward, no
look-ahead — a trade is entered the first bar a setup reclaims, then simulated with a stop below the
flush low and the **neckline as the target** by default):

```bash
./scripts/backtest.sh --timeframe 1d --history-bars 1000
./scripts/backtest.sh --timeframe 1wk --history-bars 600 --csv trades.csv
./scripts/backtest.sh --timeframe 1d --target measured_move        # neckline + (neckline - stop)
./scripts/backtest.sh --timeframe 1d --target r_multiple --r-target 2   # fixed 2:1 exits
./scripts/backtest.sh --timeframe 1d --stop atr --atr-mult 3.5 --target measured_move  # volatility stop
```

Reports per-ticker + overall: trades, win %, avg R (expectancy), total R, profit factor, max drawdown
(R), avg bars held. Uses the same `detection` thresholds as live, so tuning `config.yaml` and
re-running shows the impact. **Caveats:** ignores slippage/commissions/dividends, one position per
signal, no position sizing — results are indicative, not guarantees.

**What the backtest found.** On a volatile universe the setup is strongly positive *in-sample*
(profit factor ~3–4.6) but **breaks even to slightly negative out-of-sample** across every threshold
combination — the wide stop below a deep capitulation flush hurts reward:risk despite a ~60% win
rate. No robust *mechanical* edge held forward, which is why the bot ships as a **discretionary
finder** (see the note at the top). Large-caps rarely flush, so a flush-reclaim finder is best pointed
at higher-volatility names.

### Parameter sweep

Grid-search detection thresholds and rank by backtested edge, with an out-of-sample split so you don't
just curve-fit:

```bash
./scripts/backtest.sh --timeframe 1d \
  --sweep flush_atr_mult=1.5,2.0,3.0 --sweep reclaim_window=4,6,8 \
  --objective total_r --oos-split 0.3
```

Each combo is backtested, then trades are split by entry date into in-sample (older) and out-of-sample
(newest `--oos-split` fraction). Results rank by the `--objective` on **in-sample**, showing OOS
side by side. **Read it right:** a combo whose OOS metrics collapse was overfit (ignore it); prefer a
broad *plateau* of settings that hold up in both samples, not a single sharp peak. The sweep finds
candidates — it doesn't prove an edge. Any promising combo goes into `config.yaml` for live use.

## Multi-timeframe confirmation

A daily double-bottom is higher-conviction when the weekly trend agrees. With `mtf.require: true`
(config), a **daily** alert only fires if the weekly close is above its `sma_window`-period SMA at the
confirmation date (weekly alerts aren't gated — they *are* the higher timeframe). If the weekly
disagrees the daily signal is suppressed (not re-alerted later). The same gate is applied in the
backtest so measured results match live; toggle it off to compare:

```bash
./scripts/backtest.sh --timeframe 1d --no-mtf     # without the weekly filter
./scripts/backtest.sh --timeframe 1d              # with it (default)
```

On strongly-trending names the filter mostly reduces drawdown (few trades removed); on a choppier
universe it filters more. Configure under `mtf:` in `config.yaml`.

## Risk & position sizing

Alerts and the backtest use a **fixed-fractional** sizing model configured under `risk:` in
`config.yaml` (default: $10k account, 1% risk per trade, 25% max position). For each signal the entry
is the reclaim close and the stop sits just below the flush low, so:

```
shares = floor(account_equity x risk_per_trade_pct / (entry - stop))   # capped at max_position_pct
```

Every alert appends a **Suggested size** line (share count, $ risk, position value). The backtest can
express results in dollars via a sequential fixed-fractional equity curve:

```bash
./scripts/backtest.sh --timeframe 1d --equity 10000 --risk-pct 0.01
# -> final equity, total return, CAGR, max drawdown %
```

Caveat: the $ curve compounds trades sequentially and ignores slippage, commissions, dividends, and
concurrent-position capital limits — indicative, not a live P&L guarantee.

## Signal journal (live validation)

See how the bot's *fired* alerts actually played out vs the backtest expectancy — read-only, never
sends or mutates state:

```bash
./scripts/journal.sh                     # all fired signals
./scripts/journal.sh --since 2026-07-02  # only post-go-live signals
./scripts/journal.sh --csv journal.csv
```

It reads alerted patterns from `ddbot.sqlite3`, replays each signal's forward price to label it
**win / loss / timeout / open** (neckline target vs stop below the flush low), and prints live
win-rate / avg R / profit factor next to the backtest reference. Open positions show unrealized R
(marked `*`). Use
`--since` to exclude the seeded historical baseline and focus on genuine forward signals. Small live
samples aren't conclusive — this is for tracking, not proof.

## Risks & limitations

- **No validated mechanical edge** — the setup breaks even out-of-sample (see Backtesting); treat
  alerts as *candidates to review on the chart*, not signals to trade blindly.
- **False positives are inherent** — the prominence, steep-undercut, volume, and clean-reclaim gates
  mitigate, not eliminate.
- **yfinance** is unofficial, has no SLA, and can be delayed or gap; data is split/dividend-adjusted
  (`auto_adjust=True`).
- **Repaint safety** — only closed bars are used; `drop_forming_bar` trades same-day confirmation for
  safety (see config comments).
- **Manual confirmation is advised before any trade** — detection is probabilistic and execution is
  intentionally *not* automated.

## Roadmap

Done: multi-timeframe confirmation, chart images in alerts, backtesting engine + parameter sweep
(with out-of-sample guard), risk/position sizing, signal journal. Next: more patterns (triple bottom,
inverse H&S, ascending triangle) · fundamental overlay · execution (semi-auto → auto with kill
switch). The `DataProvider`, `Alerter`, and `Pattern` seams exist so these extend without rewrites.
