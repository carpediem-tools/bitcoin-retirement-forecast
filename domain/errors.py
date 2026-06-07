"""Business errors raised by the pure domain layer.

Each error carries a stable English ``code`` (UPPER_SNAKE) so an outer HTTP
layer can map it to a response WITHOUT this module importing Flask (CLAUDE.md
purity rule: ``domain/`` depends on nothing external). Wiring these codes to
the HTTP transport is deliberately NOT done here.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base of all pure-domain business errors. Stable ``code`` for the HTTP map."""

    code: str = "DOMAIN_ERROR"


class InsufficientHistoryError(DomainError):
    """Not enough closed months to compute ``mm_anchor`` (Agrégation §4.3, §5).

    Theoretical only with a series starting in 2010, but enforced so a truncated
    base fails loudly instead of silently shortening the MM window. Carries the
    available/required depths for diagnostics.
    """

    code = "INSUFFICIENT_HISTORY"

    def __init__(
        self, available_months: int, required_months: int, window_years: int
    ) -> None:
        self.available_months = available_months
        self.required_months = required_months
        self.window_years = window_years
        super().__init__(
            f"INSUFFICIENT_HISTORY: {available_months} closed months available, "
            f"{required_months} required for MM_WINDOW_YEARS={window_years} "
            f"((W-1)*12 + 24)."
        )
