"""Aggregation stage (pure) — Spec Agrégation v1.3 / Spec technique 8 §3.6.

Turns the contiguous monthly-close series (Synchro output) into the annual
quantities that drive the projection: rolling annual mean, rolling ARR, the
anchoring moving average ``mm_anchor``, the projection anchor, and the additive
``annual_history`` consumed by the DTO.

Pure stage: stdlib only (dataclasses, datetime) + domain.models + domain.errors.
No Flask / sqlite3 / requests / config — ``domain/`` depends on nothing external
(CLAUDE.md). No I/O: the §6.2 ``AGG_MM_ANCHOR`` INFO log belongs to the calling
layer, which has ``mm_anchor`` and ``arr_series`` in the returned result.
"""

from __future__ import annotations

from datetime import date
from typing import Sequence

from domain.errors import InsufficientHistoryError
from domain.models import AggregationResult, AnnualHistoryPoint, MonthlyClose

# Centralized Bear integrity constant (Agrégation §3.2/§7): NEVER on BearConstants
# / domain.constants (the engine consumes the scalar mm_anchor and is window-
# agnostic). Adjustable per release, never a user setting; sweepable {4, 6, 8}
# in test via the Aggregator constructor.
MM_WINDOW_YEARS = 6

# Rolling window of the annual mean / ARR base (Agrégation §4.1/§4.2). Distinct
# from MM_WINDOW_YEARS: this is the 12-month closed window, not the ARR count.
ROLLING_MONTHS = 12

MonthlyCloses = Sequence[MonthlyClose]


class Aggregator:
    """Computes the aggregation contract + diagnostics from monthly closes.

    ``mm_window_years`` defaults to the centralized ``MM_WINDOW_YEARS`` and is
    overridable for the test sweep only (the engine stays unchanged: it reads
    ``mm_anchor`` as a scalar).
    """

    def __init__(self, mm_window_years: int = MM_WINDOW_YEARS) -> None:
        self._w = mm_window_years

    @property
    def required_depth_months(self) -> int:
        # DERIVED from the window, never hard-coded (Agrégation §4.3): the oldest
        # ARR sits (W-1)*12 months back and needs its own 24-month lookback.
        return (self._w - 1) * 12 + 24

    def aggregate(self, closes: MonthlyCloses) -> AggregationResult:
        series = sorted(closes, key=lambda c: c.month)
        n = len(series)
        required = self.required_depth_months
        if n < required:
            raise InsufficientHistoryError(
                available_months=n,
                required_months=required,
                window_years=self._w,
            )

        prices = [c.price for c in series]

        def rolling_avg(i: int) -> float:
            # §4.1: simple arithmetic mean of the 12 closes ending at index i.
            window = prices[i - ROLLING_MONTHS + 1 : i + 1]
            return sum(window) / ROLLING_MONTHS

        def rolling_arr(i: int) -> float:
            # §4.2: this year's rolling mean over last year's, minus 1.
            return rolling_avg(i) / rolling_avg(i - ROLLING_MONTHS) - 1

        last = n - 1
        # §4.3 / Fig 8.2: W ARRs spaced 12 months, NON-OVERLAPPING (option lisse),
        # ordered oldest -> newest so arr_series[0] sits at mm_window_start.
        sample_indices = [last - k * 12 for k in range(self._w - 1, -1, -1)]
        arr_series = tuple(rolling_arr(i) for i in sample_indices)
        mm_anchor = sum(arr_series) / self._w
        mm_window_start = series[sample_indices[0]].month

        # §4.4: anchor = last closed month; projection starts at anchor_year + 1.
        rolling_annual_avg = rolling_avg(last)
        anchor_year = series[last].month.year
        anchor_price = rolling_annual_avg  # ≠ reference_price (Flux KPI) — never merge.

        annual_history = self._annual_history(series, anchor_year, anchor_price)

        return AggregationResult(
            anchor_year=anchor_year,
            anchor_price=anchor_price,
            mm_anchor=mm_anchor,
            rolling_annual_avg=rolling_annual_avg,
            arr_series=arr_series,
            mm_window_start=mm_window_start,
            annual_history=annual_history,
        )

    def _annual_history(
        self, series: list[MonthlyClose], anchor_year: int, anchor_price: float
    ) -> tuple[AnnualHistoryPoint, ...]:
        # §4.7: civil-year means (Jan->Dec), DISTINCT from the rolling mean.
        by_year: dict[int, list[float]] = {}
        for c in series:
            by_year.setdefault(c.month.year, []).append(c.price)

        # A civil year is complete iff it carries all 12 monthly closes; an
        # incomplete non-anchor year is excluded (§5).
        civil_avg: dict[int, float] = {
            y: sum(p) / len(p) for y, p in by_year.items() if len(p) == ROLLING_MONTHS
        }

        points: list[AnnualHistoryPoint] = []
        for year in range(min(by_year), anchor_year + 1):
            if year == anchor_year:
                # §4.7 anchor coincidence: the anchor row price IS anchor_price
                # (rolling mean) — single source of truth, not the civil mean.
                price = anchor_price
            elif year in civil_avg:
                price = civil_avg[year]
            else:
                continue

            # arr_reel(Y) = price(Y) / civil_avg(Y-1) - 1 (pilot J35 = L35/L34-1);
            # undefined (NaN) when the prior civil year is absent/incomplete.
            prev = civil_avg.get(year - 1)
            arr_reel = price / prev - 1 if prev is not None else float("nan")
            points.append(
                AnnualHistoryPoint(year=year, arr_reel=arr_reel, nominal_price=price)
            )
        return tuple(points)
