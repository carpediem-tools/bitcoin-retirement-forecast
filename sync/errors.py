"""Synchronisation business errors (Synchro v1.3 §4.3, §4.9; ST7 §5).

Each carries the stable ``code`` from the spec's error table — the same string
used in the ERROR-level log line — so the orchestrator can map it straight to
the matching ``DEGRADED_*`` ``sync_status`` without re-deriving it.
"""

from __future__ import annotations


class SyncError(Exception):
    """Base of the blocking synchronisation failures (Synchro §4.3)."""

    code: str = "SYNC_ERR"


class SyncApiError(SyncError):
    """Network / HTTP / rate-limit failure -> ``DEGRADED_API`` (Synchro §4.3)."""

    code = "SYNC_API_ERR"


class SyncStructError(SyncError):
    """``prices`` missing or malformed -> ``DEGRADED_STRUCT`` (Synchro §4.3)."""

    code = "SYNC_STRUCT_ERR"


class SyncGranularityError(SyncError):
    """Median interval far from ~24h -> ``DEGRADED_GRANULARITY`` (Synchro §4.3)."""

    code = "SYNC_GRANULARITY_ERR"
