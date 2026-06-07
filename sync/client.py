"""CoinGecko HTTP client (Synchro v1.3 §4.1, §4.9; ST7 §4.3).

One ``market_chart`` call per launch, no retry. ``timeout=(5, 10)`` is
MANDATORY (connect, read) — ``requests`` has no default timeout (ST7 §9,
verified). Keyless against api.coingecko.com by default (standard nominal
mode — NOT degraded); pro-api.coingecko.com with the ``x-cg-demo-api-key``
header only when an optional ``COINGECKO_API_KEY`` is provided.
"""

from __future__ import annotations

import os

import requests
from requests.exceptions import RequestException

from sync.errors import SyncApiError

BASE_URL_KEYLESS = "https://api.coingecko.com/api/v3"
BASE_URL_PRO = "https://pro-api.coingecko.com/api/v3"

# (connect, read) — ST7 §4.3 / CLAUDE.md: mandatory, requests has no default.
TIMEOUT = (5, 10)


class CoinGeckoClient:
    """Performs the single CoinGecko ``market_chart`` request per launch.

    ``api_key`` defaults to the optional ``COINGECKO_API_KEY`` env var when not
    given explicitly — never required, only stabilises the keyless rate limit.
    """

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key if api_key is not None else os.environ.get("COINGECKO_API_KEY")

    @property
    def _base_url(self) -> str:
        return BASE_URL_PRO if self._api_key else BASE_URL_KEYLESS

    def fetch_market_chart(self, days: int = 365) -> dict:
        """Fetch ``/coins/bitcoin/market_chart?vs_currency=usd&days=...``.

        No retry (Synchro §4.9): network errors, HTTP errors and unparsable
        bodies all collapse into ``SyncApiError`` -> ``DEGRADED_API``.
        """
        url = f"{self._base_url}/coins/bitcoin/market_chart"
        params = {"vs_currency": "usd", "days": days}
        headers = {"x-cg-demo-api-key": self._api_key} if self._api_key else None
        try:
            response = requests.get(url, params=params, headers=headers, timeout=TIMEOUT)
            response.raise_for_status()
            return response.json()
        except (RequestException, ValueError) as exc:
            raise SyncApiError(str(exc)) from exc
