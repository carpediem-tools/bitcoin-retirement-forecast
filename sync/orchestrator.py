"""Synchronisation orchestration (Synchro v1.3 §4.9, §6.2; ST7 §2).

Chains client -> validator -> deriver -> reconciler -> interpolator, produces
``sync_status`` plus metadata, and handles degraded mode. Keyless is the
standard nominal mode and must never be wired as a DEGRADED_* state.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sync.errors import SyncError
from sync.validator import SyncWarning

log = logging.getLogger("btc_forecast.sync")

# Synchro §4.6: the window treated is the 12 most recent CLOSED months.
WINDOW_MONTHS = 12
DAYS_REQUESTED = 365

# Blocking-error code -> sync_status (Synchro §6.2 / ST7 §5).
_DEGRADED_STATUS_BY_ERROR_CODE = {
    "SYNC_API_ERR": "DEGRADED_API",
    "SYNC_STRUCT_ERR": "DEGRADED_STRUCT",
    "SYNC_GRANULARITY_ERR": "DEGRADED_GRANULARITY",
}

# Non-blocking warning code -> sync_status when the call otherwise succeeds.
_WARN_STATUS_BY_WARNING_CODE = {
    "SYNC_VOLUME_WARN": "OK_WARN_VOLUME",
    "SYNC_STALE_WARN": "OK_WARN_STALE",
}


@dataclass(frozen=True)
class SyncResult:
    """Synchronisation outcome — payload of ``GET /api/sync-status`` (§6.2 / ST7 §4.2)."""

    sync_status: str
    last_sync_date: str | None
    interpolated_months: tuple[str, ...]
    missing_months: tuple[str, ...]


class SyncOrchestrator:
    """Runs the full synchronisation pipeline for one launch."""

    def __init__(self, client, validator, deriver, reconciler, interpolator, meta_dao) -> None:
        self._client = client
        self._validator = validator
        self._deriver = deriver
        self._reconciler = reconciler
        self._interpolator = interpolator
        self._meta_dao = meta_dao

    def run(self, now: datetime | None = None) -> SyncResult:
        """Execute synchronisation and return the sync status + metadata (§4.9)."""
        now = now if now is not None else datetime.now(timezone.utc)
        window = self._closed_months_window(now)

        status, warnings = self._fetch_and_reconcile(window, now)

        # Step 2 runs unconditionally — even in degraded mode — on any gap
        # bounded by two `real` closes (§4.9, ST7 §5).
        interpolated, missing = self._interpolator.interpolate(window)

        if status.startswith("DEGRADED"):
            last_sync_date = self._meta_dao.get_meta("last_sync_date")
        else:
            last_sync_date = now.isoformat()
            self._meta_dao.set_meta("last_sync_date", last_sync_date)
            log.info("SYNC_OK: %d months processed, %s", len(window), last_sync_date)

        for warning in warnings:
            log.warning(warning.log_message)

        return SyncResult(
            sync_status=status,
            last_sync_date=last_sync_date,
            interpolated_months=interpolated,
            missing_months=missing,
        )

    def _fetch_and_reconcile(
        self, window: list[str], now: datetime
    ) -> tuple[str, tuple[SyncWarning, ...]]:
        """Fetch + validate + derive + reconcile; return ``(sync_status, warnings)``.

        Any blocking failure (network/HTTP, structure, granularity) is caught
        here and mapped straight to its ``DEGRADED_*`` status — the existing
        base is left untouched (no reconciliation runs).
        """
        try:
            payload = self._client.fetch_market_chart(DAYS_REQUESTED)
            warnings = self._validator.validate(payload, now)
        except SyncError as exc:
            log.error("%s: %s", exc.code, exc)
            return _DEGRADED_STATUS_BY_ERROR_CODE[exc.code], ()

        derived = self._deriver.derive(payload["prices"], now)
        self._reconciler.reconcile(derived, window)

        # Spec defines no combined code for volume+freshness together; the
        # first warning encountered (volume, then freshness) sets the status —
        # both are logged regardless (§6.2).
        status = "OK"
        if warnings:
            status = _WARN_STATUS_BY_WARNING_CODE[warnings[0].code]
        return status, warnings

    @staticmethod
    def _closed_months_window(now: datetime, count: int = WINDOW_MONTHS) -> list[str]:
        """Return the ``count`` most recent closed months as 'YYYY-MM', oldest first (§4.6)."""
        months = []
        year, month = now.year, now.month
        for _ in range(count):
            month -= 1
            if month == 0:
                month, year = 12, year - 1
            months.append(f"{year:04d}-{month:02d}")
        return list(reversed(months))
