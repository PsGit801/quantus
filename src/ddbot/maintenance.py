"""One-off DB maintenance — clean pre-dedup duplicate alerts.

The initial seed ran before per-neckline dedup existed, leaving several alerted rows for
the same breakout (same ticker/timeframe/confirm_date). This collapses each such group to
the single strongest (highest-prominence) pattern so the signal journal reflects reality.

    python -m ddbot.maintenance          # backs up the DB, then dedupes
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
from collections import defaultdict

from .config import load_config


def _prominence(row: sqlite3.Row) -> float:
    base = min(row["b1_low"], row["b2_low"])
    return (row["neckline"] - base) / base if base else 0.0


def dedupe_alerted(conn: sqlite3.Connection) -> int:
    """Keep the highest-prominence alerted pattern per (ticker, timeframe, confirm_date);
    delete the rest. Returns the number of rows removed."""
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT pattern_id, ticker, timeframe, confirm_date, neckline, b1_low, b2_low "
        "FROM patterns WHERE alerted = 1 AND confirm_date IS NOT NULL"
    ).fetchall()

    groups: dict[tuple, list] = defaultdict(list)
    for r in rows:
        groups[(r["ticker"], r["timeframe"], r["confirm_date"])].append(r)

    to_delete: list[str] = []
    for rs in groups.values():
        if len(rs) <= 1:
            continue
        ranked = sorted(rs, key=_prominence, reverse=True)
        to_delete += [r["pattern_id"] for r in ranked[1:]]  # keep the strongest

    for pid in to_delete:
        conn.execute("DELETE FROM patterns WHERE pattern_id = ?", (pid,))
    conn.commit()
    return len(to_delete)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Clean duplicate seed alerts from the DB")
    p.add_argument("--config", default="config/config.yaml")
    args = p.parse_args(argv)

    db = load_config(args.config).db_path

    # Checkpoint the WAL so the backup captures the latest state, then back up.
    con = sqlite3.connect(db)
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    con.close()
    shutil.copyfile(db, db + ".bak")

    con = sqlite3.connect(db)
    removed = dedupe_alerted(con)
    con.close()
    print(f"backed up to {db}.bak  |  removed {removed} duplicate alerted row(s)")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
