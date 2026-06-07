"""Reconciliation — step 1 (Synchro v1.3 §4.7; ST7 §9).

Writes ``real`` closes for every closed month of the window that CoinGecko
could derive this run. Absent months are left to step 2 (Interpolator).
"""

from __future__ import annotations

from datetime import datetime, timezone


class Reconciler:
    """Reconciles derived ``real`` closes into the persisted series (step 1)."""

    def __init__(self, dao) -> None:
        self._dao = dao

    def reconcile(self, derived: dict[str, float], window: list[str]) -> None:
        """Persist ``derived`` closes for the closed months of ``window`` (§4.7).

        The three-way rule — absent -> write ``real``, ``interpolated`` ->
        overwrite with ``real``, ``real`` -> frozen — collapses to a single
        unconditional upsert per month: the ``real`` > ``interpolated`` guard
        is enforced INSIDE ``MonthlyCloseDAO.upsert_monthly_close``, not here.
        """
        updated_at = datetime.now(timezone.utc).isoformat()
        for month in window:
            price = derived.get(month)
            if price is not None:
                self._dao.upsert_monthly_close(month, price, "real", updated_at)
