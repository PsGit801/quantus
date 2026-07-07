# ddbot — Double-Bottom Detection & Alert Bot (Phase 1 MVP)

Pulls OHLCV for a watchlist (the **Magnificent 7** by default) on **daily and weekly**
timeframes, detects **double-bottom** chart patterns, waits for a bullish confirmation candle that
closes above the neckline, and alerts to **Telegram + Discord** with an **annotated candlestick
chart** showing the two bottoms, the neckline, and the green breakout candle.

Each timeframe is scanned independently and fires its own alert (weekly is a stronger, rarer signal).

## How it works

```
hermes cron ──> python -m ddbot.run ──> yfinance ──> detect ──> SQLite state ──> confirm ──> alert
```

Each run is self-contained and **idempotent**: pending patterns are persisted to SQLite, so a
confirmation that arrives days later is caught, and a confirmed setup is never alerted twice. Only
**closed** bars are ever acted on (the current-day daily bar repaints, so it is dropped by default).

### Detection logic (`src/ddbot/patterns/double_bottom.py`)

1. **Swing lows** — a bar is a swing low if its low is the min over ±`swing_k` bars.
2. **Candidate pairs** (B1 before B2) — spacing within `[min_bars_between, max_bars_between]`, and
   the two lows within `bottom_tol_pct` of each other.
3. **Neckline** — the highest high strictly between the bottoms; the "W" must have depth
   (`min_prominence_pct` above the bottoms). This is the main false-positive filter.
4. **Prior downtrend** (optional) — price must have declined into B1.
5. **Confirmation** — first closed candle after B2 that closes above `neckline × (1 + buffer)`, is
   green (`close > open`), **and** carries volume ≥ `volume_factor` × the prior `volume_avg_window`-bar
   average (weak-volume breakouts are skipped until a stronger one appears).
6. **Invalidation** — close below the lower bottom, or expiry after `max_bars_between` bars.
7. **Dedup** — candidates whose necklines sit within ~2% are collapsed to the strongest, so one
   breakout = one alert.

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

Covers swing detection, clean-W detection, near-misses (dissimilar bottoms, low prominence),
confirmation (bullish breakout), non-confirmation (red breakout candle), invalidation, and the
end-to-end idempotency guarantee.

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
look-ahead — a trade is entered the first bar a pattern confirms, then simulated with a stop below the
bottoms and a measured-move target):

```bash
./scripts/backtest.sh --timeframe 1d --history-bars 1000
./scripts/backtest.sh --timeframe 1wk --history-bars 600 --csv trades.csv
./scripts/backtest.sh --timeframe 1d --target r_multiple --r-target 2   # fixed 2:1 exits
./scripts/backtest.sh --no-volume        # test sensitivity to the volume gate
```

Reports per-ticker + overall: trades, win %, avg R (expectancy), total R, profit factor, max drawdown
(R), avg bars held. Uses the same `detection` thresholds as live, so tuning `config.yaml` and
re-running shows the impact. **Caveats:** ignores slippage/commissions/dividends, one position per
signal, no position sizing — results are indicative, not guarantees.

### Parameter sweep

Grid-search detection thresholds and rank by backtested edge, with an out-of-sample split so you don't
just curve-fit:

```bash
./scripts/backtest.sh --timeframe 1d \
  --sweep volume_factor=1.0,1.5,2.0 --sweep min_prominence_pct=0.05,0.08 \
  --objective profit_factor --oos-split 0.3
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
is the breakout close and the stop sits below the bottoms, so:

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

## Risks & limitations

- **False positives are inherent** — prominence + similarity + confirmation gates mitigate, not eliminate.
- **yfinance** is unofficial, has no SLA, and can be delayed or gap; data is split/dividend-adjusted
  (`auto_adjust=True`).
- **Repaint safety** — only closed bars are used; `drop_forming_bar` trades same-day confirmation for
  safety (see config comments).
- **Manual confirmation is advised before any trade** — detection is probabilistic. Execution is
  intentionally *not* part of Phase 1.

## Roadmap

P2 volume + multi-timeframe confirmation, chart images in alerts · P3 more patterns (triple bottom,
inverse H&S, ascending triangle) · P4 backtesting engine · P5 risk management (ATR stops, sizing) ·
P6 fundamental overlay · P7 execution (semi-auto → auto with kill switch).

The `DataProvider`, `Alerter`, and `Pattern` seams exist so these extend without rewrites.
