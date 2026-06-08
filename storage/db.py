"""SQLite connection and idempotent schema initialisation (ST7 §3.1, §7).

The DDL is the verbatim schema of the Infra spec. ``init_schema`` is safe to
re-run: every statement uses ``CREATE TABLE IF NOT EXISTS``.
"""

from __future__ import annotations

import csv
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

# Verbatim DDL — ST7 §3.1. Do not edit without a schema_version bump.
SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS monthly_close (
    month      TEXT PRIMARY KEY,                 -- 'YYYY-MM' (mois civil clos)
    price      REAL NOT NULL,                    -- clôture mensuelle USD (IEEE-754 double)
    origin     TEXT NOT NULL CHECK (origin IN ('real','interpolated')),
    updated_at TEXT NOT NULL                     -- horodatage ISO 8601 UTC
);

CREATE TABLE IF NOT EXISTS app_meta (            -- last_sync_date, schema_version
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS forecast_params (     -- profil unique persisté (pas de multi-profil V1)
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def get_connection(db_path: Path | str) -> sqlite3.Connection:
    """Open a SQLite connection with row access by column name."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(db_path: Path | str) -> None:
    """Create the schema if needed. Idempotent — safe to call on every launch."""
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA_DDL)
        conn.commit()
    finally:
        conn.close()


def seed_from_csv(db_path: Path | str, csv_path: Path | str) -> int:
    """Load ``csv_path`` (header ``month,price``) into ``monthly_close``.

    Uses ``INSERT OR IGNORE`` on the ``month`` primary key so existing rows
    (notably ``origin='real'`` rows from sync) are never overwritten. All
    seeded rows get ``origin='real'``. Returns the number of rows actually
    inserted (net), not the number of rows processed.
    """
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append((row["month"], float(row["price"]), "real", now))

    conn = get_connection(db_path)
    try:
        before = conn.execute("SELECT COUNT(*) FROM monthly_close").fetchone()[0]
        conn.executemany(
            "INSERT OR IGNORE INTO monthly_close (month, price, origin, updated_at)"
            " VALUES (?, ?, ?, ?)",
            rows,
        )
        conn.commit()
        after = conn.execute("SELECT COUNT(*) FROM monthly_close").fetchone()[0]
        return after - before
    finally:
        conn.close()
