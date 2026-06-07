"""CoinGecko HTTP client (Synchro v1.3 §4.1, §4.9; ST7 §4.3).

One ``market_chart`` call per launch, no retry. ``timeout=(5, 10)`` is
MANDATORY (connect, read). Keyless against api.coingecko.com by default;
pro-api.coingecko.com with the ``x-cg-demo-api-key`` header only when an
optional key is provided.
"""

from __future__ import annotations


class CoinGeckoClient:
    """Performs the single CoinGecko ``market_chart`` request per launch."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key

    def fetch_market_chart(self, days: int = 365) -> dict:
        """Fetch ``/coins/bitcoin/market_chart?vs_currency=usd&days=...``.

        Must use ``timeout=(5, 10)`` and perform no retry.
        """
        raise NotImplementedError
