"""Monthly-close derivation (Synchro v1.3 §4.2, §4.4, §4.5).

Converts UTC millisecond timestamps to (year, month) keys and keeps the last
point of each month. UTC everywhere — never a naive datetime (ST7 §9).
"""

from __future__ import annotations


class MonthlyCloseDeriver:
    """Derives monthly closes from the raw price series."""

    def derive(self, prices: list[list[float]]) -> dict[str, float]:
        """Map ``[[ts_ms, price], ...]`` to ``{'YYYY-MM': close_price}``."""
        raise NotImplementedError
