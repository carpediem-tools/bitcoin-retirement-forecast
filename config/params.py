"""Pydantic validation of USER forecast-flow parameters (ST7 §3.2).

Declarative field constraints follow Flux v1.1 (e.g. ``initial_stack >= 0``).
The cross-field rule (``dca_end_year`` required when ``monthly_dca > 0``, Flux §5)
is left as a stub for the flow brief — no business logic is wired here yet.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


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
