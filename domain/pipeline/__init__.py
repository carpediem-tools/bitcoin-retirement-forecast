"""Pipeline orchestration + DTO assembly (pure) — Spec technique 8 §2.5, §3.6, §3.7, §9.

Chains Aggregator -> PriceEngine -> FlowEngine and assembles the
``ForecastExportDTO`` (semantic mirror of the pilot's ``_Export`` sheet).

The sole inter-referential join is ``nominal_price`` (PriceEngineResult ->
FlowEngineInput, ST8 §3.7); ``anchor_year`` is a shared lineage emitted by
Aggregator to both downstream stages — never a join.

``runway`` traverses as-is (``int`` or ``float('inf')``): the "Infinity"
string conversion is an HTTP serialization concern, not the pipeline's.

Pure stage: stdlib (math, collections.abc) + domain.constants + domain.models +
domain.aggregation + domain.price_engine + domain.flow_engine + config.params
(FlowParams — boundary type, same documented exception as flow_engine, CLAUDE.md).
"""

import math
from collections.abc import Sequence

from config.params import FlowParams
from domain.aggregation import Aggregator
from domain.constants import BEAR_CONSTANTS, BearConstants
from domain.flow_engine import FlowEngine, FlowEngineInput
from domain.models import (
    AggregationResult,
    FlowResult,
    ForecastExportDTO,
    ForecastParams,
    MonthlyClose,
    PriceEngineResult,
    SeriesPoint,
)
from domain.price_engine import PriceEngine

MonthlyCloses = Sequence[MonthlyClose]


class ForecastPipeline:
    """Chains the three pure stages and assembles the export DTO (ST8 §2.5)."""

    def __init__(self, constants: BearConstants = BEAR_CONSTANTS):
        self._c = constants

    def run(self, closes: MonthlyCloses, flow_params: FlowParams) -> ForecastExportDTO:
        agg = Aggregator().aggregate(closes)
        price = PriceEngine(self._c).project(agg)
        flow = FlowEngine(self._c).run(
            FlowEngineInput(
                anchor_year=agg.anchor_year,
                nominal_price={p.year: p.nominal_price for p in price.series},
                params=flow_params,
            )
        )
        return self._assemble_dto(agg, price, flow, flow_params)

    def _assemble_dto(
        self,
        agg: AggregationResult,
        price: PriceEngineResult,
        flow: FlowResult,
        flow_params: FlowParams,
    ) -> ForecastExportDTO:
        flow_by_year = {f.year: f for f in flow.series}
        inflation = flow_params.inflation_rate

        def real_price(nominal: float, year: int) -> float | None:
            try:
                result = nominal * (1 + inflation) ** (agg.anchor_year - year)
            except (OverflowError, ZeroDivisionError):
                return None
            if not math.isfinite(result) or result > 1e12 or result < 1e-3:
                return None
            return result

        def nan_to_none(v: float) -> float | None:
            return None if math.isnan(v) else v

        series: list[SeriesPoint] = []

        # — Historical block (annual_history, includes the anchor year, ST8 §3.6) —
        for h in agg.annual_history:
            series.append(
                SeriesPoint(
                    year=h.year,
                    n=h.year - agg.anchor_year,
                    kind="historical",
                    arr_real=nan_to_none(h.arr_reel),
                    arr_theo=None,
                    nominal_price=h.nominal_price,
                    real_price=real_price(h.nominal_price, h.year),
                    cost_inflation=None,
                    cost_lifestyle=None,
                    btc_out=None,
                    stack=None,
                    portfolio=None,
                )
            )

        # — Projection block (anchor_year+1 .. HORIZON, ST8 §3.6) —
        for py in price.series:
            if py.year <= agg.anchor_year:
                continue   # the anchor row is already carried by annual_history
            fy = flow_by_year[py.year]
            series.append(
                SeriesPoint(
                    year=py.year,
                    n=py.year - agg.anchor_year,
                    kind="projection",
                    arr_real=None,
                    arr_theo=py.arr_theo,
                    nominal_price=py.nominal_price,
                    real_price=real_price(py.nominal_price, py.year),
                    cost_inflation=fy.cdv_inflation,
                    cost_lifestyle=fy.cdv_train,
                    btc_out=fy.btc_out,
                    stack=fy.stack,
                    portfolio=fy.portfolio,
                )
            )

        params = ForecastParams(
            current_year=agg.anchor_year + 1,
            anchor_year=agg.anchor_year,
            initial_stack=flow_params.initial_stack,
            monthly_expenses=flow_params.monthly_expenses,
            reference_price=flow_params.reference_price,
            inflation_rate=flow_params.inflation_rate,
            plateau_arr=self._c.PLATEAU_ARR,
            spending_growth_rate=flow_params.spending_growth_rate,
            plateau_year=self._c.PLATEAU_YEAR,
            mm_anchor=agg.mm_anchor,
            runway=flow.runway,
            current_portfolio=flow_params.initial_stack * flow_params.reference_price,
        )

        return ForecastExportDTO(params=params, series=tuple(series))
