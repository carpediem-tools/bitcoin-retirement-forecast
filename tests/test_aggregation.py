"""Aggregation — composition validation on hand-computed data (Agrégation v1.3).

No end-to-end oracle: each datum is built so the rolling means/ARRs and the MM6
can be checked by hand. The series uses a per-year constant close, so a December
rolling 12-month window equals that civil year's mean; each annual ARR is then a
clean year-over-year ratio.
"""

import math

import pytest

from datetime import date

from domain.aggregation import MM_WINDOW_YEARS, Aggregator
from domain.errors import InsufficientHistoryError
from domain.models import MonthlyClose

# Per-year constant close. Year-over-year ratios are 0.10, 0.20, ... 0.60, so the
# six non-overlapping annual ARRs (2019..2024) average to mm_anchor = 0.35.
YEAR_PRICE = {
    2018: 1000.0,
    2019: 1100.0,    # ARR 0.10 vs 2018
    2020: 1320.0,    # ARR 0.20 vs 2019
    2021: 1716.0,    # ARR 0.30 vs 2020
    2022: 2402.4,    # ARR 0.40 vs 2021
    2023: 3603.6,    # ARR 0.50 vs 2022
    2024: 5765.76,   # ARR 0.60 vs 2023
}


def _full_year_months(start: int, end: int):
    for y in range(start, end + 1):
        for m in range(1, 13):
            yield (y, m)


def _series(year_price=YEAR_PRICE, start=2018, end=2024) -> list[MonthlyClose]:
    # Jan(start)..Dec(end) inclusive — contiguous. 2018..2024 = 84 months (W=6 floor).
    return [
        MonthlyClose(date(y, m, 1), year_price[y], "real")
        for (y, m) in _full_year_months(start, end)
    ]


def test_nominal_anchor_and_mm6():
    result = Aggregator().aggregate(_series())

    # §4.4: anchor = last closed month (Dec 2024); anchor_price = rolling mean.
    assert result.anchor_year == 2024
    assert result.anchor_price == pytest.approx(5765.76)
    assert result.rolling_annual_avg == pytest.approx(5765.76)

    # §4.3: mm_anchor = mean of the six annual ARRs 0.10..0.60.
    assert result.mm_anchor == pytest.approx(0.35)


def test_arr_series_is_W_nonoverlapping_annual():
    result = Aggregator().aggregate(_series())

    # Exactly MM_WINDOW_YEARS ARRs, oldest -> newest.
    assert len(result.arr_series) == MM_WINDOW_YEARS == 6
    # Each value is a distinct calendar-year ratio: overlapping (e.g. monthly)
    # sampling could not reproduce the clean 0.10..0.60 ladder.
    assert result.arr_series == pytest.approx((0.10, 0.20, 0.30, 0.40, 0.50, 0.60))
    # Oldest ARR sits 60 months (5 years) before the anchor's December — the
    # (W-1)*12 spacing of non-overlapping annual windows.
    assert result.mm_window_start == date(2019, 12, 1)


def test_insufficient_history_raises():
    # 83 closed months < 84 required for W=6 -> business error, no computation.
    short = _series()[:-1]
    assert len(short) == 83

    with pytest.raises(InsufficientHistoryError) as exc:
        Aggregator().aggregate(short)

    assert exc.value.code == "INSUFFICIENT_HISTORY"
    assert exc.value.required_months == 84
    assert exc.value.available_months == 83


def test_required_depth_is_derived_per_window():
    # (W-1)*12 + 24 — never hard-coded (Agrégation §4.3).
    assert Aggregator(mm_window_years=4).required_depth_months == 60
    assert Aggregator(mm_window_years=6).required_depth_months == 84
    assert Aggregator(mm_window_years=8).required_depth_months == 108


def test_window_sweep_changes_mm_without_touching_engine():
    # W=4 keeps the four most recent annual ARRs (2021..2024) -> mean 0.45.
    result = Aggregator(mm_window_years=4).aggregate(_series())
    assert result.arr_series == pytest.approx((0.30, 0.40, 0.50, 0.60))
    assert result.mm_anchor == pytest.approx(0.45)
    assert result.mm_window_start == date(2021, 12, 1)


def test_annual_history_civil_means_and_arr():
    hist = {p.year: p for p in Aggregator().aggregate(_series()).annual_history}

    assert set(hist) == {2018, 2019, 2020, 2021, 2022, 2023, 2024}
    # First year has no prior civil year -> arr_reel undefined (NaN).
    assert math.isnan(hist[2018].arr_reel)
    assert hist[2018].nominal_price == pytest.approx(1000.0)
    # Year-over-year civil ARRs.
    assert hist[2019].arr_reel == pytest.approx(0.10)
    assert hist[2024].arr_reel == pytest.approx(0.60)


def test_partial_anchor_year_uses_rolling_not_civil():
    # Anchor year is partial (Jan-Jun 2025). §4.7: the anchor row price is the
    # rolling mean (anchor_price), NOT the incomplete civil mean.
    year_price = {**YEAR_PRICE, 2025: 7000.0}
    closes = _series(year_price, 2018, 2024) + [
        MonthlyClose(date(2025, m, 1), year_price[2025], "real") for m in range(1, 7)
    ]

    result = Aggregator().aggregate(closes)
    assert result.anchor_year == 2025
    # Rolling mean spans Jul2024..Jun2025 = (P2024 + P2025) / 2.
    expected_rolling = (year_price[2024] + year_price[2025]) / 2
    assert result.anchor_price == pytest.approx(expected_rolling)

    hist = {p.year: p for p in result.annual_history}
    assert hist[2025].nominal_price == pytest.approx(expected_rolling)
    assert hist[2025].nominal_price != pytest.approx(7000.0)  # not the civil mean
    # arr_reel(anchor) = anchor_price / civil_avg(2024) - 1 (pilot J35 = L35/L34-1).
    assert hist[2025].arr_reel == pytest.approx(expected_rolling / year_price[2024] - 1)
    # Completed prior year keeps its civil ARR.
    assert hist[2024].arr_reel == pytest.approx(0.60)
