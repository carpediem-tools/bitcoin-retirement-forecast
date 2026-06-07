"""Application configuration (host, port, filesystem paths).

Network binding is restricted to 127.0.0.1 (single-user, no auth — ST7 §7).
Default port is 8000 with incremental bind fallback handled at launch (run.py).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Loopback only — never 0.0.0.0 (ST7 §7).
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEFAULT_DB_PATH = PROJECT_ROOT / "forecast.db"


@dataclass(frozen=True)
class AppConfig:
    """Runtime application configuration."""

    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    db_path: Path = field(default=DEFAULT_DB_PATH)

    @classmethod
    def load(cls) -> "AppConfig":
        """Build the configuration from the environment.

        Only the local port is overridable (``BTC_FORECAST_PORT``); the host is
        pinned to loopback by design.
        """
        port = int(os.environ.get("BTC_FORECAST_PORT", DEFAULT_PORT))
        return cls(port=port)
