"""ForecastPipeline._assemble_dto composition tests (ST8 §2.5, §3.6, §3.7, §9).

Isolation: hand-built minimal AggregationResult / PriceEngineResult / FlowResult
fixtures — no real closes, no SQLite, no end-to-end oracle.
"""

import math
from datetime import date

from config.params import FlowParams
from domain.models import (
    AggregationResult,
    AnnualHistoryPoint,
    FlowResult,
    FlowYear,
    ProjectedYear,
    PriceEngineResult,
)
from domain.pipeline import ForecastPipeline


def _agg() -> AggregationResult:
    return AggregationResult(
        anchor_year=2025,
        anchor_price=101700.0,
        mm_anchor=0.3613,
        rolling_annual_avg=101700.0,
        arr_series=(),
        mm_window_start=date(2019, 1, 1),
        annual_history=(
            AnnualHistoryPoint(year=2024, arr_reel=float("nan"), nominal_price=50000.0),
            AnnualHistoryPoint(year=2025, arr_reel=0.5417, nominal_price=101700.0),
        ),
    )


def _price() -> PriceEngineResult:
    return PriceEngineResult(
        anchor_year=2025,
        anchor_price=101700.0,
        series=(
            ProjectedYear(year=2025, arr_theo=None, nominal_price=101700.0),
            ProjectedYear(year=2026, arr_theo=0.210231258, nominal_price=123080.52),
        ),
    )


def _flow(runway=float("inf")) -> FlowResult:
    return FlowResult(
        series=(
            FlowYear(year=2025, btc_in=1.0, btc_out=0.0, cdv_inflation=60000.0,
                     cdv_train=60000.0, stack=1.0, portfolio=101700.0),
            FlowYear(year=2026, btc_in=0.0, btc_out=0.6, cdv_inflation=60000.0,
                     cdv_train=60000.0, stack=0.4, portfolio=49232.21),
        ),
        runway=runway,
    )


def _flow_params() -> FlowParams:
    return FlowParams.model_construct(
        initial_stack=1.0,
        reference_price=90000.0,
        monthly_expenses=5000.0,
        inflation_rate=0.06,
        spending_growth_rate=0.0,
        btc_spending_start_year=2026,
        monthly_dca=0.0,
        dca_growth_rate=0.0,
        dca_end_year=None,
    )


def _dto(runway=float("inf")):
    pipeline = ForecastPipeline()
    return pipeline._assemble_dto(_agg(), _price(), _flow(runway), _flow_params())


def test_cas1_nan_to_none():
    dto = _dto()
    point = dto.series[0]

    assert point.year == 2024
    assert point.kind == "historical"
    assert point.arr_reel is None
    assert point.stack is None


def test_cas2_real_price_formula():
    dto = _dto()
    by_year = {(p.year, p.kind): p for p in dto.series}

    historical_2024 = by_year[(2024, "historical")]
    assert math.isclose(historical_2024.real_price, 53000.0, rel_tol=1e-9, abs_tol=1e-2)

    projection_2026 = by_year[(2026, "projection")]
    assert math.isclose(projection_2026.real_price, 123080.52 / 1.06, rel_tol=1e-9, abs_tol=1e-2)


def test_cas3_current_portfolio_guard():
    dto = _dto()

    assert dto.params.current_portfolio == 90000.0
    assert dto.params.current_portfolio != 101700.0


def test_cas4_runway_propagation_infinite():
    dto = _dto(runway=float("inf"))

    assert dto.params.runway == float("inf")


def test_cas5_runway_propagation_finite():
    dto = _dto(runway=2)

    assert dto.params.runway == 2


def test_cas6_series_structure():
    dto = _dto()

    assert len(dto.series) == 3
    assert dto.series[0].kind == "historical"
    assert dto.series[2].kind == "projection"
    assert dto.series[2].arr_theo == 0.210231258
    assert dto.series[2].btc_out == 0.6
