"""Response validation (Synchro v1.3 §4.3; ST7 §5).

Blocking checks (structure, granularity) raise ``SyncStructError`` /
``SyncGranularityError`` -> ``DEGRADED_*``. Non-blocking checks (volume,
freshness) are collected as ``SyncWarning`` and let synchronisation proceed —
the success criterion is the derivability of the closed monthly closes, not
the raw point count (Synchro §4.3).
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime, timezone

from sync.errors import SyncGranularityError, SyncStructError

# ~24h between consecutive daily points, ±10 % (Synchro §4.3) — insensitive to
# leap years/months, the determining check that a monthly grouping is valid.
GRANULARITY_TARGET_MS = 86_400_000
GRANULARITY_TOLERANCE = 0.10

VOLUME_MIN = 360
VOLUME_MAX = 370

# "Slightly late" window (Synchro §5): 0 days = fresh (no warning), > 6 days is
# outside the defined non-blocking range (granularity/volume would already
# have caught a genuinely broken feed).
STALE_MIN_DAYS = 1
STALE_MAX_DAYS = 6


@dataclass(frozen=True)
class SyncWarning:
    """One non-blocking finding — ephemeral UI notice + permanent log line (§6.2)."""

    code: str            # SYNC_VOLUME_WARN | SYNC_STALE_WARN
    log_message: str


class ResponseValidator:
    """Validates the raw CoinGecko payload before derivation (Synchro §4.3)."""

    def validate(self, payload: dict, now: datetime | None = None) -> tuple[SyncWarning, ...]:
        """Run the four checks; raise on a blocking failure, else return warnings."""
        prices = self._check_structure(payload)
        self._check_granularity(prices)

        warnings = []
        volume_warning = self._check_volume(prices)
        if volume_warning is not None:
            warnings.append(volume_warning)
        stale_warning = self._check_freshness(prices, now)
        if stale_warning is not None:
            warnings.append(stale_warning)
        return tuple(warnings)

    @staticmethod
    def _check_structure(payload: dict) -> list:
        # Detects an API schema change / corrupted, unreadable response.
        prices = payload.get("prices") if isinstance(payload, dict) else None
        if not isinstance(prices, list) or not prices:
            raise SyncStructError(f"received: {repr(payload)[:200]}")

        first = prices[0]
        is_number_pair = (
            isinstance(first, (list, tuple))
            and len(first) == 2
            and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in first)
        )
        if not is_number_pair:
            raise SyncStructError(f"received: {first!r}")
        return prices

    @staticmethod
    def _check_granularity(prices: list) -> None:
        # Median interval, not mean: robust to the rare missing/duplicated day.
        timestamps = [point[0] for point in prices]
        intervals = [b - a for a, b in zip(timestamps, timestamps[1:])]
        if not intervals:
            return
        median = statistics.median(intervals)
        if abs(median - GRANULARITY_TARGET_MS) > GRANULARITY_TARGET_MS * GRANULARITY_TOLERANCE:
            raise SyncGranularityError(
                f"median interval = {median / 3_600_000:.1f}h, expected ~24h"
            )

    @staticmethod
    def _check_volume(prices: list) -> SyncWarning | None:
        n = len(prices)
        if VOLUME_MIN <= n <= VOLUME_MAX:
            return None
        return SyncWarning(
            code="SYNC_VOLUME_WARN",
            log_message=f"SYNC_VOLUME_WARN: {n} points received, expected 360-370 — continuing",
        )

    @staticmethod
    def _check_freshness(prices: list, now: datetime | None) -> SyncWarning | None:
        now = now if now is not None else datetime.now(timezone.utc)
        latest_ts = max(point[0] for point in prices)
        latest_date = datetime.fromtimestamp(latest_ts / 1000, tz=timezone.utc)
        age_days = (now - latest_date).days
        if STALE_MIN_DAYS <= age_days <= STALE_MAX_DAYS:
            return SyncWarning(
                code="SYNC_STALE_WARN",
                log_message=(
                    f"SYNC_STALE_WARN: latest point dated {latest_date.date()}, "
                    f"i.e. {age_days} days old — continuing"
                ),
            )
        return None
