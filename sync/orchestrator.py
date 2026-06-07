"""Synchronisation orchestration (Synchro v1.3 §4.9, §6.2; ST7 §2).

Chains client -> validator -> deriver -> reconciler -> interpolator, produces
``sync_status`` plus metadata, and handles degraded mode. Keyless is the
standard nominal mode and must never be wired as a DEGRADED_* state.
"""

from __future__ import annotations


class SyncOrchestrator:
    """Runs the full synchronisation pipeline for one launch."""

    def __init__(
        self,
        client: "object",
        validator: "object",
        deriver: "object",
        reconciler: "object",
        interpolator: "object",
    ) -> None:
        self._client = client
        self._validator = validator
        self._deriver = deriver
        self._reconciler = reconciler
        self._interpolator = interpolator

    def run(self) -> dict:
        """Execute synchronisation and return the sync status + metadata."""
        raise NotImplementedError
