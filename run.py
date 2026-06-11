"""Launch entry point (ST7 §6).

Initialises the SQLite schema, builds the Flask app, then serves it with
waitress on 127.0.0.1 (default port 8000, incremental bind fallback if busy).
A browser tab is opened only AFTER the server is bound and listening.

The Flask dev server is never used — waitress only (ST7 §1, §9).
"""

from __future__ import annotations

import logging
import threading
import time
import webbrowser

from waitress import create_server

from config.app_config import AppConfig
from storage.db import init_schema
from web.app import create_app

log = logging.getLogger("btc_forecast.run")

# Number of consecutive ports to try before giving up (8000, 8001, ...).
PORT_FALLBACK_ATTEMPTS = 20
# Small delay before opening the browser, so waitress is already listening.
BROWSER_OPEN_DELAY_S = 1.0


def create_server_with_fallback(app, host: str, start_port: int):
    """Create a waitress server, trying successive ports if one is busy.

    Returns ``(server, port)``. ``create_server`` binds immediately, so a busy
    port raises OSError, which we catch to try the next port.
    """
    last_error: OSError | None = None
    for offset in range(PORT_FALLBACK_ATTEMPTS):
        port = start_port + offset
        try:
            server = create_server(app, host=host, port=port)
            if port != start_port:
                log.info("Port %d busy — bound to %d instead", start_port, port)
            return server, port
        except OSError as exc:
            last_error = exc
            log.warning("Port %d unavailable, trying %d", port, port + 1)
    raise RuntimeError(
        f"No free port in range {start_port}..{start_port + PORT_FALLBACK_ATTEMPTS - 1}"
    ) from last_error


def open_browser_when_ready(url: str) -> None:
    """Open the default browser tab once the server is up."""
    time.sleep(BROWSER_OPEN_DELAY_S)
    webbrowser.open(url)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    config = AppConfig.load()

    # Idempotent schema init — creates forecast.db on first launch (ST7 §7).
    init_schema(config.db_path)

    from pathlib import Path as _Path

    from storage.db import seed_from_csv as _seed

    _seed_csv = _Path(__file__).resolve().parent / "data" / "seed_monthly_closes.csv"
    if _seed_csv.exists():
        _n = _seed(config.db_path, _seed_csv)
        if _n > 0:
            log.info("Seed : %d clôtures historiques chargées", _n)
        else:
            log.debug("Seed : base déjà peuplée, skip")
    else:
        log.warning("Seed CSV introuvable (%s) — lancement sans historique", _seed_csv)

    # Sync CoinGecko → SQLite (1 call/launch, degraded mode if KO).
    # SyncOrchestrator takes its collaborators (client/validator/deriver/
    # reconciler/interpolator/meta_dao), not a db_path — wired here from a
    # dedicated connection, closed before the app's per-request pool opens.
    from storage.dao import AppMetaDAO, MonthlyCloseDAO
    from storage.db import get_connection
    from sync.client import CoinGeckoClient
    from sync.deriver import MonthlyCloseDeriver
    from sync.interpolator import Interpolator
    from sync.orchestrator import SyncOrchestrator
    from sync.reconciler import Reconciler
    from sync.validator import ResponseValidator

    log.info("Synchronisation des clôtures mensuelles…")
    try:
        conn = get_connection(config.db_path)
        try:
            dao = MonthlyCloseDAO(conn)
            sync_result = SyncOrchestrator(
                client=CoinGeckoClient(),
                validator=ResponseValidator(),
                deriver=MonthlyCloseDeriver(),
                reconciler=Reconciler(dao),
                interpolator=Interpolator(dao),
                meta_dao=AppMetaDAO(conn),
            ).run()
            log.info("Sync terminée : %s", sync_result.sync_status)
        finally:
            conn.close()
    except Exception as exc:
        log.error("Sync échouée : %s — l'app démarre en mode dégradé", exc)

    app = create_app(config)
    server, port = create_server_with_fallback(app, config.host, config.port)
    url = f"http://{config.host}:{port}/"

    log.info("Serving on %s (waitress)", url)
    threading.Thread(
        target=open_browser_when_ready, args=(url,), daemon=True
    ).start()

    server.run()


if __name__ == "__main__":
    main()
