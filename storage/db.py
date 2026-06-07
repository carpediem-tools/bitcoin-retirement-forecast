"""SQLite connection and idempotent schema initialisation (ST7 §3.1, §7).

The DDL is the verbatim schema of the Infra spec. ``init_schema`` is safe to
re-run: every statement uses ``CREATE TABLE IF NOT EXISTS``.
"""

from __future__ import annotations

import sqlite3
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
