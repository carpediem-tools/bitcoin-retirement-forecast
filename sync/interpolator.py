"""Interpolation — step 2 (Synchro v1.3 §4.8).

Linear interpolation of gaps bounded by two ``real`` closes. Applied even in
degraded mode for any gap that is bounded (ST7 §5).
"""

from __future__ import annotations


class Interpolator:
    """Fills bounded gaps in the monthly-close series."""

    def interpolate(self) -> list[str]:
        """Interpolate bounded gaps; return the list of interpolated months."""
        raise NotImplementedError
