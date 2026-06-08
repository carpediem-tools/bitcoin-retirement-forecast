"""FlowEngine composition tests (Flux v1.1 / ST8 §2.3, §3.4-§3.5).

No end-to-end oracle: constant prices + hand-verifiable parameters injected
via ``FlowParams.model_construct()`` (bypasses cross-field validation, which
needs ``anchor_year``/``HORIZON`` context not relevant to these unit cases).
"""

import math

from config.params import FlowParams
from domain.flow_engine import FlowEngine, FlowEngineInput
from domain.models import FlowResult


def const_prices(price, anchor=2025, horizon=2072):
    return {y: float(price) for y in range(anchor, horizon + 1)}


def _run(params, anchor_year=2025, price=100_000):
    inp = FlowEngineInput(
        anchor_year=anchor_year,
        nominal_price=const_prices(price, anchor=anchor_year),
        params=params,
    )
    return FlowEngine().run(inp)


def _by_year(result):
    return {fy.year: fy for fy in result.series}


def test_cas1_drawdown_pur():
    p = FlowParams.model_construct(
        initial_stack=1.0,
        reference_price=100_000,
        monthly_expenses=5000,
        inflation_rate=0,
        spending_growth_rate=0,
        btc_spending_start_year=2026,
        monthly_dca=0,
        dca_growth_rate=0,
        dca_end_year=None,
    )
    by_year = _by_year(_run(p))

    assert by_year[2025].stack == 1.0
    assert math.isclose(by_year[2026].stack, 0.4)
    assert math.isclose(by_year[2027].stack, -0.2)


def test_cas2_dca_pur():
    p = FlowParams.model_construct(
        initial_stack=0,
        reference_price=100_000,
        monthly_expenses=1,
        inflation_rate=0,
        spending_growth_rate=0,
        btc_spending_start_year=2060,
        monthly_dca=1000,
        dca_growth_rate=0,
        dca_end_year=2027,
    )
    by_year = _by_year(_run(p))

    assert math.isclose(by_year[2025].btc_in, 0.12)
    assert math.isclose(by_year[2025].stack, 0.12)
    assert math.isclose(by_year[2026].stack, 0.24)
    assert math.isclose(by_year[2027].stack, 0.36)
    assert math.isclose(by_year[2028].stack, 0.36)


def test_cas3_chevauchement_dca_drawdown():
    p = FlowParams.model_construct(
        initial_stack=0,
        reference_price=100_000,
        monthly_expenses=500,
        inflation_rate=0,
        spending_growth_rate=0,
        btc_spending_start_year=2026,
        monthly_dca=1000,
        dca_growth_rate=0,
        dca_end_year=2027,
    )
    by_year = _by_year(_run(p))

    assert math.isclose(by_year[2025].stack, 0.12)
    assert math.isclose(by_year[2026].stack, 0.18)
    assert math.isclose(by_year[2027].stack, 0.24)


def test_cas4_runway_fini():
    p = FlowParams.model_construct(
        initial_stack=1.0,
        reference_price=100_000,
        monthly_expenses=5000,
        inflation_rate=0,
        spending_growth_rate=0,
        btc_spending_start_year=2026,
        monthly_dca=0,
        dca_growth_rate=0,
        dca_end_year=None,
    )
    result = _run(p)

    assert isinstance(result, FlowResult)
    assert result.runway == 2


def test_cas5_runway_infini():
    p = FlowParams.model_construct(
        initial_stack=1.0,
        reference_price=100_000,
        monthly_expenses=1,
        inflation_rate=0,
        spending_growth_rate=0,
        btc_spending_start_year=2026,
        monthly_dca=0,
        dca_growth_rate=0,
        dca_end_year=None,
    )
    result = _run(p)

    assert result.runway == float("inf")
    assert all(fy.stack > 0 for fy in result.series)


def test_cas6_post_epuisement():
    p = FlowParams.model_construct(
        initial_stack=1.0,
        reference_price=100_000,
        monthly_expenses=5000,
        inflation_rate=0,
        spending_growth_rate=0,
        btc_spending_start_year=2026,
        monthly_dca=0,
        dca_growth_rate=0,
        dca_end_year=None,
    )
    by_year = _by_year(_run(p))

    assert 2028 in by_year
    assert math.isclose(by_year[2028].stack, -0.8)
    assert by_year[2028].portfolio < 0


def test_cas7_inflation_et_spending_growth_composes():
    p = FlowParams.model_construct(
        initial_stack=1.0,
        reference_price=100_000,
        monthly_expenses=5000,
        inflation_rate=0.5,
        spending_growth_rate=0.5,
        btc_spending_start_year=2026,
        monthly_dca=0,
        dca_growth_rate=0,
        dca_end_year=None,
    )
    result = _run(p)
    by_year = _by_year(result)

    assert by_year[2025].btc_out == 0.0

    assert math.isclose(by_year[2026].cdv_inflation, 90_000)
    assert math.isclose(by_year[2026].cdv_train, 135_000)
    assert math.isclose(by_year[2026].btc_out, 1.35)
    assert math.isclose(by_year[2026].stack, -0.35)
    assert result.runway == 1
