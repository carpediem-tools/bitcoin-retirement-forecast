"""Response validation (Synchro v1.3 §4.3; ST7 §5).

Blocking checks (structure, granularity) raise DEGRADED_*; non-blocking checks
(volume, freshness) emit warnings and let synchronisation proceed.
"""

from __future__ import annotations


class ResponseValidator:
    """Validates the raw CoinGecko payload before derivation."""

    def validate(self, payload: dict) -> None:
        """Run blocking and non-blocking checks on the response."""
        raise NotImplementedError
