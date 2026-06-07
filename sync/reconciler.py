"""Reconciliation — step 1 (Synchro v1.3 §4.7; ST7 §9).

Writes ``real`` closes, overwrites any ``interpolated`` value, and never
overwrites an existing ``real`` (the ``real`` guard is enforced at the DAO).
"""

from __future__ import annotations


class Reconciler:
    """Reconciles derived ``real`` closes into the persisted series."""

    def reconcile(self, derived: dict[str, float]) -> None:
        """Persist derived ``real`` closes (step 1)."""
        raise NotImplementedError
