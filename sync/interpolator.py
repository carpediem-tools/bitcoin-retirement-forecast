"""Interpolation — step 2 (Synchro v1.3 §4.8).

Linear interpolation of gaps bounded by two ``real`` closes. Applied even in
degraded mode for any gap that is bounded (ST7 §5) — runs unconditionally
after step 1, independent of whether the CoinGecko call succeeded this time.
"""

from __future__ import annotations

from datetime import datetime, timezone


def _shift_month(month: str, delta: int) -> str:
    """Return ``month`` ('YYYY-MM') shifted by ``delta`` calendar months."""
    year, month_num = (int(part) for part in month.split("-"))
    total = year * 12 + (month_num - 1) + delta
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


class Interpolator:
    """Fills gaps in ``window`` bounded by two ``real`` closes (§4.8)."""

    def __init__(self, dao) -> None:
        self._dao = dao

    def interpolate(self, window: list[str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Interpolate bounded gaps in ``window``; return ``(interpolated, missing)``.

        A maximal run of absent months is filled only when BOTH its immediate
        calendar neighbours exist and are ``real`` (§4.8 — interpolation never
        anchors on another interpolated value, by construction it can't: a
        bounded zone is always filled in one block). Otherwise the run stays
        absent and is reported in ``missing``.
        """
        updated_at = datetime.now(timezone.utc).isoformat()
        interpolated: list[str] = []
        missing: list[str] = []

        i, n_months = 0, len(window)
        while i < n_months:
            if self._dao.get_monthly_close(window[i]) is not None:
                i += 1
                continue

            run_start = i
            while i < n_months and self._dao.get_monthly_close(window[i]) is None:
                i += 1
            run = window[run_start:i]

            bound_a = self._dao.get_monthly_close(_shift_month(run[0], -1))
            bound_b = self._dao.get_monthly_close(_shift_month(run[-1], +1))

            if bound_a is not None and bound_a.origin == "real" \
                    and bound_b is not None and bound_b.origin == "real":
                # V_A + (V_B - V_A) * k / N — N = span in months, k = 1..N-1.
                v_a, v_b, n = bound_a.price, bound_b.price, len(run) + 1
                for k, month in enumerate(run, start=1):
                    value = v_a + (v_b - v_a) * k / n
                    self._dao.upsert_monthly_close(month, value, "interpolated", updated_at)
                    interpolated.append(month)
            else:
                missing.extend(run)

        return tuple(interpolated), tuple(missing)
