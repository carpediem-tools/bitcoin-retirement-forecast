"""CoinGecko synchronisation module (Spec Synchronisation v1.3, ST7 §2).

Keyless by default (standard nominal mode — NOT a DEGRADED_* state). One
CoinGecko call per launch, no retry; failures fall back to DEGRADED_* while
preserving the existing database.

Decomposition (ST7 §2): CoinGeckoClient, ResponseValidator,
MonthlyCloseDeriver, Reconciler, Interpolator, SyncOrchestrator.
"""
