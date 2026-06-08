"""Pydantic validation of USER forecast-flow parameters (ST7 §3.2).

Declarative field constraints follow Flux v1.1 (e.g. ``initial_stack >= 0``).
The cross-field rule (``dca_end_year`` required when ``monthly_dca > 0``, Flux §5)
is left as a stub for the flow brief — no business logic is wired here yet.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, model_validator


class FlowParams(BaseModel):
    """User-supplied Flux parameters, validated at the entry boundary (ST8 §4.1).

    Cross-field rules reference ``anchor_year``/``HORIZON``, injected via the
    Pydantic validation ``context`` by the caller (POST /api/params, Spec 7).
    Aggregation-derived figures (``anchor_year``, ``anchor_price``, ``mm_anchor``)
    are NOT revalidated here — they come from a trusted upstream module.
    """

    model_config = ConfigDict(frozen=True)

    initial_stack: float = Field(ge=0)
    reference_price: float = Field(gt=0)       # KPI current_portfolio (≠ anchor_price)
    monthly_expenses: float = Field(gt=0)
    inflation_rate: float = Field(ge=-1)
    spending_growth_rate: float = Field(ge=-1)
    btc_spending_start_year: int
    monthly_dca: float = Field(default=0, ge=0)
    dca_growth_rate: float = Field(default=0, ge=-1)
    dca_end_year: int | None = None

    @model_validator(mode="after")
    def _validate_cross_fields(self, info: ValidationInfo) -> "FlowParams":
        if self.monthly_dca > 0 and self.dca_end_year is None:
            raise ValueError("DCA_END_REQUIRED: dca_end_year is required when monthly_dca > 0")

        context = info.context or {}
        anchor_year = context.get("anchor_year")
        horizon = context.get("horizon")
        if anchor_year is not None and horizon is not None:
            for field, year in (
                ("btc_spending_start_year", self.btc_spending_start_year),
                ("dca_end_year", self.dca_end_year),
            ):
                if year is not None and not (anchor_year <= year <= horizon):
                    raise ValueError(
                        f"YEAR_OUT_OF_RANGE: {field}={year} must be within "
                        f"[{anchor_year}, {horizon}]"
                    )

        return self


class ForecastParams(BaseModel):
    """User-supplied forecast parameters, validated on input/load.

    Field ranges mirror Flux v1.1. Cross-field validation is intentionally not
    implemented in this scaffold (see module docstring).
    """

    initial_stack: float = Field(ge=0)
    monthly_dca: float = Field(ge=0)
    dca_growth_rate: float
    dca_end_year: int | None = None  # required when monthly_dca > 0 (Flux §5)
    btc_spending_start_year: int
    monthly_living_cost: float = Field(gt=0)
    spending_growth_rate: float
    inflation_rate: float

    # TODO(flow): cross-field validator — dca_end_year mandatory if monthly_dca > 0.
