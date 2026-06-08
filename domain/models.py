"""Boundary structures of the domain pipeline (Spec technique 8 §3.2/§3.3).

Frozen dataclasses, English field names, prices/rates as ``float`` (IEEE-754
double). Pure declarative module: stdlib only (dataclasses, datetime, typing),
no dependency on flask/sqlite3/requests/pydantic/config (CLAUDE.md "Frontière
config/ vs domain/").
"""

from dataclasses import dataclass
from datetime import date
from typing import Literal


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


@dataclass(frozen=True)
class ForecastParams:
    """DTO params block — mirrors the key/value row of ``_Export`` (ST8 §3.6).

    NOT to be confused with ``config.params.FlowParams`` (Pydantic, validates
    user input): this is the frozen DTO carrier assembled by the pipeline.
    """

    current_year: int            # = anchor_year + 1
    anchor_year: int
    initial_stack: float         # stack_btc        (F5)
    monthly_expenses: float      # depenses_mois    (C6)
    reference_price: float       # prix_ref_2025    (F6) — KPI ; ≠ anchor_price
    inflation_rate: float        # inflation        (C7)
    plateau_arr: float           # plateau_arr      (F7) — BearConstants.PLATEAU_ARR
    spending_growth_rate: float  # train_de_vie     (C8)
    plateau_year: int            # annee_plateau    (F8) — BearConstants.PLATEAU_YEAR
    mm_anchor: float             # mm4 -> mm_anchor (C12)
    runway: int | float          # runway           (F12) ; "Infinity" at HTTP serialization
    current_portfolio: float     # portfolio_actuel (F11) = initial_stack x reference_price


@dataclass(frozen=True)
class SeriesPoint:
    """One row of the DTO ``series`` table — mirrors ``_Export`` rows 4-68 (ST8 §3.6)."""

    year: int                    # année        (col A <- H)
    n: int                       # n            (col B <- I) = year - anchor_year
    kind: Literal["historical", "projection"]
    arr_reel: float | None       # arr_reel     (col C <- J) — historical
    arr_theo: float | None       # arr_theo     (col D <- K) — projection
    nominal_price: float         # prix_nominal (col E <- L)
    real_price: float            # prix_reel    (col F <- M) = nominal x (1+inflation)^(anchor_year - year)
    cdv_inflation: float | None  # cdv_inflation (col G <- N) — projection
    cdv_train: float | None      # cdv_train    (col H <- O) — projection
    btc_out: float | None        # dep_btc      (col I <- P) — projection
    stack: float | None          # stack_btc    (col J <- Q) — projection
    portfolio: float | None      # portfolio    (col K <- R) — projection


@dataclass(frozen=True)
class ForecastExportDTO:
    """Pipeline output — semantic mirror of ``_Export`` (ST8 §3.6)."""

    params: ForecastParams
    series: tuple[SeriesPoint, ...]   # annual_history[0].year .. HORIZON
