"""Boundary structures of the domain pipeline (Spec technique 8 §3.2/§3.3).

Frozen dataclasses, English field names, prices/rates as ``float`` (IEEE-754
double). Pure declarative module: stdlib only (dataclasses, datetime, typing),
no dependency on flask/sqlite3/requests/pydantic/config (CLAUDE.md "Frontière
config/ vs domain/").
"""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class MonthlyClose:
    """One closed calendar month (Synchro v1.3 §3.1) — Aggregation input.

    ``month`` is the first day of the closed month (calendar arithmetic stays in
    the domain, the 'YYYY-MM' string lives at the storage boundary). ``real`` and
    ``interpolated`` are equivalent for aggregation (Agrégation §3.1).
    """

    month: date
    price: float          # USD close (IEEE-754 double)
    origin: str           # 'real' | 'interpolated'


@dataclass(frozen=True)
class AnnualHistoryPoint:
    """One historical year (2009 .. anchor) — Aggregation v1.3 additive series."""

    year: int
    arr_reel: float
    nominal_price: float


@dataclass(frozen=True)
class AggregationResult:
    """Boundary 1 — Aggregation output / Engine input (ST8 §3.2).

    The engine only consumes ``anchor_year``, ``anchor_price`` and ``mm_anchor``;
    the remaining fields are diagnostic (UI/logs) or feed the DTO.
    """

    # — Contract consumed by the Engine (Moteur v1.0 §3.1) —
    anchor_year: int          # last closed month ; projection starts at anchor_year + 1
    anchor_price: float       # USD — = rolling_annual_avg ; ≠ reference_price (Flux KPI)
    mm_anchor: float          # rate — mean of the last MM_WINDOW_YEARS annual ARRs
    # — Diagnostic (Aggregation §6.2), UI/logs, NOT consumed by the Engine —
    rolling_annual_avg: float                    # USD — rolling annual mean (= anchor_price)
    arr_series: tuple[float, ...]                # the MM_WINDOW_YEARS ARRs feeding mm_anchor
    mm_window_start: date                        # date of the oldest ARR used
    # — Historical series (Aggregation v1.3 additive) — consumed by the DTO —
    annual_history: tuple[AnnualHistoryPoint, ...]   # 2009 .. anchor_year


@dataclass(frozen=True)
class ProjectedYear:
    """Boundary carrier of the join (ST8 §3.3).

    ``nominal_price`` is the SOLE inter-referential join value. ``arr_theo`` is
    ``None`` at the anchor year (which carries the real observed price).
    """

    year: int                    # absolute calendar year (no counter C — Moteur §4.1)
    arr_theo: float | None       # theoretical ARR ; None at the anchor year
    nominal_price: float         # USD — capitalisation


@dataclass(frozen=True)
class PriceEngineResult:
    """Engine output (ST8 §3.3): anchor + projected series up to HORIZON."""

    anchor_year: int
    anchor_price: float
    series: tuple[ProjectedYear, ...]   # anchor (arr_theo=None) .. HORIZON (2072)


@dataclass(frozen=True)
class FlowYear:
    """One projected year of the Flux series (ST8 §3.5)."""

    year: int
    btc_in: float
    btc_out: float
    cdv_inflation: float
    cdv_train: float
    stack: float
    portfolio: float


@dataclass(frozen=True)
class FlowResult:
    """FlowEngine output (ST8 §3.5): series from anchor_year to HORIZON + runway."""

    series: tuple[FlowYear, ...]
    runway: int | float   # years, or float('inf') if the stack never goes negative
