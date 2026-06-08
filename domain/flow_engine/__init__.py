"""Flow engine stage (pure) — Spec Flux v1.1 / Spec technique 8 §2.3, §3.4, §3.5.

Subsidy mechanics: ``FlowEngine`` derives ``C = year - anchor_year`` itself and
loops from ``anchor_year`` to ``HORIZON`` (no counter on the price side — the
join carries only ``nominal_price``, anti-bug V4 guard). DEC-DCA-03: the spend
that drives the drawdown COMPOSES inflation and lifestyle growth
(``cdv_train = cdv_inflation × (1+spending_growth)^C``).

Stack assumed non-monotone (DCA/drawdown overlap possible); after exhaustion
the projection continues into negative territory (faithful to Subsidy — no
re-positivation logic). Runway = first ``stack < 0`` flip minus ``anchor_year``,
else ``inf``.

Pure stage: stdlib (dataclasses, collections.abc) + domain.constants +
domain.models + config.params (FlowParams — boundary type only, no circularity:
config/ does not import flow_engine).
"""

from collections.abc import Mapping
from dataclasses import dataclass

from config.params import FlowParams
from domain.constants import BEAR_CONSTANTS, BearConstants
from domain.models import FlowResult, FlowYear


@dataclass(frozen=True)
class FlowEngineInput:
    """Boundary 2 — sole inter-referential join is ``nominal_price`` (ST8 §3.4)."""

    anchor_year: int                    # origin of C = year - anchor_year (Flux §3.3)
    nominal_price: Mapping[int, float]  # year -> nominal price (consumed as-is)
    params: FlowParams


class FlowEngine:
    """Runs the Subsidy drawdown/DCA mechanics from a FlowEngineInput."""

    def __init__(self, constants: BearConstants = BEAR_CONSTANTS):
        self._c = constants

    # — §4.1: DCA inflow, grown at dca_growth_rate over C, while year <= dca_end_year —
    def btc_in_dca(self, year: int, C: int, price: float, p: FlowParams) -> float:
        if p.monthly_dca > 0 and year <= p.dca_end_year:
            return p.monthly_dca * (1 + p.dca_growth_rate) ** C * 12 / price
        return 0.0

    # — §4.2: initial stack injected once, at the anchor —
    def btc_in_initial(self, year: int, anchor_year: int, p: FlowParams) -> float:
        return p.initial_stack if year == anchor_year else 0.0

    # — §4.3: informative — always computed —
    def cdv_inflation(self, C: int, p: FlowParams) -> float:
        return p.monthly_expenses * 12 * (1 + p.inflation_rate) ** C

    # — §4.3: drives the spend — composes inflation AND lifestyle growth (DEC-DCA-03) —
    def cdv_train(self, C: int, p: FlowParams) -> float:
        return self.cdv_inflation(C, p) * (1 + p.spending_growth_rate) ** C

    # — §4.3: BTC outflow once spending has started —
    def btc_out(self, year: int, C: int, price: float, p: FlowParams) -> float:
        if year >= p.btc_spending_start_year:
            return self.cdv_train(C, p) / price
        return 0.0

    # — §4.4-§4.6: cumulation, valuation, runway —
    def run(self, inp: FlowEngineInput) -> FlowResult:
        anchor_year = inp.anchor_year
        p = inp.params

        series = []
        cumul_in = 0.0
        cumul_out = 0.0
        runway: int | float = float("inf")

        for year in range(anchor_year, self._c.HORIZON + 1):
            C = year - anchor_year
            price = inp.nominal_price[year]

            in_ = self.btc_in_dca(year, C, price, p) + self.btc_in_initial(year, anchor_year, p)
            out = self.btc_out(year, C, price, p)
            cumul_in += in_
            cumul_out += out

            stack = cumul_in - cumul_out
            portfolio = stack * price

            if stack < 0 and runway == float("inf"):
                runway = year - anchor_year

            series.append(
                FlowYear(
                    year=year,
                    btc_in=in_,
                    btc_out=out,
                    cdv_inflation=self.cdv_inflation(C, p),
                    cdv_train=self.cdv_train(C, p),
                    stack=stack,
                    portfolio=portfolio,
                )
            )

        return FlowResult(series=tuple(series), runway=runway)
