"""Minimal SQLite DAO surface (no ORM — ST7 §1, §2).

Method bodies are intentionally not implemented in this scaffold; only the
access surface is fixed. The ``real`` > ``interpolated`` upsert guard (ST7 §9)
must be enforced in ``upsert_close`` when implemented.
"""

from __future__ import annotations

import sqlite3


class MonthlyCloseDAO:
    """Read/write access to the ``monthly_close`` series."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert_close(self, month: str, price: float, origin: str, updated_at: str) -> None:
        """Upsert a monthly close, enforcing ``real`` > ``interpolated`` (ST7 §9)."""
        raise NotImplementedError

    def get_series(self) -> list[sqlite3.Row]:
        """Return the full monthly-close series ordered chronologically."""
        raise NotImplementedError


class AppMetaDAO:
    """Key/value access to ``app_meta`` (e.g. last_sync_date, schema_version)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get(self, key: str) -> str | None:
        raise NotImplementedError

    def set(self, key: str, value: str) -> None:
        raise NotImplementedError


class ForecastParamsDAO:
    """Key/value access to the persisted single forecast profile."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get_all(self) -> dict[str, str]:
        raise NotImplementedError

    def set_all(self, values: dict[str, str]) -> None:
        raise NotImplementedError
