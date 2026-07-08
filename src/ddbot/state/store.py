"""SQLite-backed pattern store.

Persistence is what makes the bot idempotent across hermes runs: pending patterns
survive between invocations, state transitions are recorded, and the ``alerted`` flag
guarantees a confirmed setup is never alerted twice.
"""

from __future__ import annotations

import sqlite3
from datetime import date

from ..patterns.base import DoubleBottom, PatternState

_SCHEMA = """
CREATE TABLE IF NOT EXISTS patterns (
    pattern_id    TEXT PRIMARY KEY,
    ticker        TEXT NOT NULL,
    timeframe     TEXT NOT NULL,
    state         TEXT NOT NULL,
    b1_date       TEXT NOT NULL,
    b1_low        REAL NOT NULL,
    b2_date       TEXT NOT NULL,
    b2_low        REAL NOT NULL,
    peak_date     TEXT NOT NULL,
    neckline      REAL NOT NULL,
    confirm_date  TEXT,
    confirm_close REAL,
    alerted       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS watchlist (
    ticker   TEXT PRIMARY KEY,
    added_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS kv (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d is not None else None


def _parse_date(s: str | None) -> date | None:
    return date.fromisoformat(s) if s else None


def _row_to_pattern(row: sqlite3.Row) -> DoubleBottom:
    return DoubleBottom(
        ticker=row["ticker"],
        timeframe=row["timeframe"],
        b1_date=_parse_date(row["b1_date"]),
        b1_low=row["b1_low"],
        b2_date=_parse_date(row["b2_date"]),
        b2_low=row["b2_low"],
        peak_date=_parse_date(row["peak_date"]),
        neckline=row["neckline"],
        state=PatternState(row["state"]),
        confirm_date=_parse_date(row["confirm_date"]),
        confirm_close=row["confirm_close"],
    )


class PatternStore:
    def __init__(self, db_path: str):
        # timeout + WAL: the daily scanner and the Telegram sync job share this file.
        self.conn = sqlite3.connect(db_path, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def exists(self, pattern_id: str) -> bool:
        cur = self.conn.execute("SELECT 1 FROM patterns WHERE pattern_id = ?", (pattern_id,))
        return cur.fetchone() is not None

    def upsert_detected(self, p: DoubleBottom) -> bool:
        """Insert a newly detected pattern. No-op if it already exists (preserving state).

        Returns True if a new row was inserted.
        """
        cur = self.conn.execute(
            """
            INSERT OR IGNORE INTO patterns
                (pattern_id, ticker, timeframe, state, b1_date, b1_low,
                 b2_date, b2_low, peak_date, neckline, confirm_date, confirm_close, alerted)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                p.pattern_id, p.ticker, p.timeframe, p.state.value,
                _iso(p.b1_date), p.b1_low, _iso(p.b2_date), p.b2_low,
                _iso(p.peak_date), p.neckline, _iso(p.confirm_date), p.confirm_close,
            ),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def update_state(self, p: DoubleBottom) -> None:
        self.conn.execute(
            """
            UPDATE patterns
               SET state = ?, confirm_date = ?, confirm_close = ?
             WHERE pattern_id = ?
            """,
            (p.state.value, _iso(p.confirm_date), p.confirm_close, p.pattern_id),
        )
        self.conn.commit()

    def pending_patterns(self, ticker: str, timeframe: str) -> list[DoubleBottom]:
        cur = self.conn.execute(
            "SELECT * FROM patterns WHERE ticker = ? AND timeframe = ? AND state = ?",
            (ticker, timeframe, PatternState.DETECTED.value),
        )
        return [_row_to_pattern(r) for r in cur.fetchall()]

    def alerted_patterns(self) -> list[DoubleBottom]:
        """All patterns that were actually alerted (fired to the user), oldest first."""
        cur = self.conn.execute(
            "SELECT * FROM patterns WHERE alerted = 1 ORDER BY confirm_date, ticker"
        )
        return [_row_to_pattern(r) for r in cur.fetchall()]

    def is_alerted(self, pattern_id: str) -> bool:
        cur = self.conn.execute(
            "SELECT alerted FROM patterns WHERE pattern_id = ?", (pattern_id,)
        )
        row = cur.fetchone()
        return bool(row["alerted"]) if row else False

    def mark_alerted(self, pattern_id: str) -> None:
        self.conn.execute(
            "UPDATE patterns SET alerted = 1 WHERE pattern_id = ?", (pattern_id,)
        )
        self.conn.commit()

    # --- watchlist -------------------------------------------------------------

    def seed_watchlist(self, defaults: list[str]) -> None:
        """Populate the watchlist from config defaults, but only if it's empty."""
        cur = self.conn.execute("SELECT COUNT(*) AS n FROM watchlist")
        if cur.fetchone()["n"] > 0:
            return
        self.conn.executemany(
            "INSERT OR IGNORE INTO watchlist (ticker) VALUES (?)",
            [(t,) for t in defaults],
        )
        self.conn.commit()

    def list_tickers(self) -> list[str]:
        cur = self.conn.execute("SELECT ticker FROM watchlist ORDER BY added_at, ticker")
        return [r["ticker"] for r in cur.fetchall()]

    def add_ticker(self, ticker: str) -> bool:
        """Add a ticker; return True if it was newly inserted."""
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO watchlist (ticker) VALUES (?)", (ticker,)
        )
        self.conn.commit()
        return cur.rowcount > 0

    def remove_ticker(self, ticker: str) -> bool:
        """Remove a ticker; return True if a row was deleted."""
        cur = self.conn.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker,))
        self.conn.commit()
        return cur.rowcount > 0

    # --- key/value (telegram offset, transient flags) --------------------------

    def kv_get(self, key: str) -> str | None:
        cur = self.conn.execute("SELECT value FROM kv WHERE key = ?", (key,))
        row = cur.fetchone()
        return row["value"] if row else None

    def kv_set(self, key: str, value: str | None) -> None:
        if value is None:
            self.conn.execute("DELETE FROM kv WHERE key = ?", (key,))
        else:
            self.conn.execute(
                "INSERT INTO kv (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
        self.conn.commit()
