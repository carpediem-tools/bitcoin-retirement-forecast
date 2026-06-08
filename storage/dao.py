"""Minimal SQLite DAO surface (no ORM — ST7 §1, §2).

SQL is parameterised throughout, no f-string interpolation of values. ``price``
is persisted as ``REAL`` (IEEE-754 double) — never ``Decimal`` (CLAUDE.md / ST7
§9: the non-regression oracle is validated on doubles). ``MonthlyClose`` is the
boundary type already defined in ``domain.models`` — reused here, not redefined
(outer layers depend on ``domain/``, never the reverse — CLAUDE.md).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date

from config.params import FlowParams
from domain.models import MonthlyClose

# Fallback profile served by ``load_raw``/used when ``forecast_params`` is empty
# (first launch — ST7 §3.1: the table holds the single persisted profile).
DEFAULT_PARAMS: dict = {
    "initial_stack": 1.0,
    "reference_price": 101700.0,
    "monthly_expenses": 2500.0,
    "inflation_rate": 0.06,
    "spending_growth_rate": 0.05,
    "btc_spending_start_year": 2035,
    "monthly_dca": 0.0,
    "dca_growth_rate": 0.0,
    "dca_end_year": None,
}


def _row_to_monthly_close(row: sqlite3.Row) -> MonthlyClose:
    year, month = (int(part) for part in row["month"].split("-"))
    return MonthlyClose(month=date(year, month, 1), price=row["price"], origin=row["origin"])


class MonthlyCloseDAO:
    """Read/write access to the ``monthly_close`` series."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert_monthly_close(self, month: str, price: float, origin: str, updated_at: str) -> None:
        """Upsert a monthly close, enforcing ``real`` > ``interpolated`` (ST7 §9).

        An existing ``real`` row is frozen — never overwritten, not even by
        another ``real`` (Synchro §4.7: "ne rien faire, valeur figée"). Any
        other case (absent, or existing ``interpolated``) is written/replaced.
        """
        existing = self._conn.execute(
            "SELECT origin FROM monthly_close WHERE month = ?", (month,)
        ).fetchone()
        if existing is not None and existing["origin"] == "real":
            return
        self._conn.execute(
            """
            INSERT INTO monthly_close (month, price, origin, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(month) DO UPDATE SET
                price = excluded.price,
                origin = excluded.origin,
                updated_at = excluded.updated_at
            """,
            (month, price, origin, updated_at),
        )
        self._conn.commit()

    def get_monthly_closes(self, from_month: str | None = None) -> list[MonthlyClose]:
        """Return the monthly-close series in chronological order.

        ``month`` sorts lexicographically = chronologically ('YYYY-MM', ST7
        §3.1) — no calendar computation needed. ``from_month`` filters to
        months on or after that key when given.
        """
        if from_month is not None:
            rows = self._conn.execute(
                "SELECT month, price, origin FROM monthly_close WHERE month >= ? ORDER BY month",
                (from_month,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT month, price, origin FROM monthly_close ORDER BY month"
            ).fetchall()
        return [_row_to_monthly_close(row) for row in rows]

    def get_monthly_close(self, month: str) -> MonthlyClose | None:
        """Return the close for ``month`` ('YYYY-MM'), or ``None`` if absent."""
        row = self._conn.execute(
            "SELECT month, price, origin FROM monthly_close WHERE month = ?", (month,)
        ).fetchone()
        return _row_to_monthly_close(row) if row is not None else None


class AppMetaDAO:
    """Key/value access to ``app_meta`` (e.g. ``last_sync_date``, ``schema_version``)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get_meta(self, key: str) -> str | None:
        row = self._conn.execute(
            "SELECT value FROM app_meta WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row is not None else None

    def set_meta(self, key: str, value: str) -> None:
        self._conn.execute(
            """
            INSERT INTO app_meta (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        self._conn.commit()


class ForecastParamsDAO:
    """Key/value access to the persisted single forecast profile (ST7 §3.1).

    Values are JSON-encoded (``None``/``float``/``int``/``str`` all serialise
    cleanly — ``dca_end_year = None`` is stored as the JSON literal ``null``).
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save(self, params: FlowParams) -> None:
        """Upsert every field of ``params`` (already validated at input)."""
        for key, value in params.model_dump().items():
            self._conn.execute(
                """
                INSERT INTO forecast_params (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, json.dumps(value)),
            )
        self._conn.commit()

    def load(self) -> FlowParams | None:
        """Reconstruct the persisted ``FlowParams``, or ``None`` if unset.

        ``model_construct`` bypasses cross-field validation: stored values were
        already validated at the POST /api/params boundary.
        """
        raw = self._load_rows()
        return FlowParams.model_construct(**raw) if raw is not None else None

    def load_raw(self) -> dict:
        """Return the raw key/value profile, or ``DEFAULT_PARAMS`` if unset."""
        raw = self._load_rows()
        return raw if raw is not None else dict(DEFAULT_PARAMS)

    def _load_rows(self) -> dict | None:
        rows = self._conn.execute("SELECT key, value FROM forecast_params").fetchall()
        if not rows:
            return None
        return {row["key"]: json.loads(row["value"]) for row in rows}
