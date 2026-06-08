"""Flask application factory and routes (ST7 §4.1).

Wires the four routes onto the real ``domain``/``storage`` stack: connections
are opened per-request from ``config.db_path`` (loopback-only, single-user —
no pooling needed), and routes tolerate an empty database with a JSON 503
rather than raising. ``domain/`` stays pure: the ``float('inf')`` -> "Infinity"
serialisation (ST8 §9 — JSON has no native infinity) lives here, in the HTTP
layer, never in the pipeline.
"""

from __future__ import annotations

import dataclasses
import math
from pathlib import Path

from flask import Flask, jsonify, request, send_file
from pydantic import ValidationError

from config.app_config import AppConfig
from config.params import FlowParams
from domain.aggregation import Aggregator
from domain.constants import BEAR_CONSTANTS
from domain.errors import InsufficientHistoryError
from domain.models import ForecastExportDTO
from domain.pipeline import ForecastPipeline
from storage.dao import AppMetaDAO, ForecastParamsDAO, MonthlyCloseDAO
from storage.db import get_connection

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_FILE = PROJECT_ROOT / "btc_dashboard.html"


def _fix_inf(obj):
    """Replace ``float('inf')`` with the portable JSON string ``"Infinity"`` (ST8 §9)."""
    if isinstance(obj, float) and math.isinf(obj):
        return "Infinity"
    if isinstance(obj, dict):
        return {k: _fix_inf(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_fix_inf(v) for v in obj]
    return obj


def dto_to_dict(dto: ForecastExportDTO) -> dict:
    """Serialise the DTO to a JSON-ready dict, with ``runway = inf`` fixed up.

    ``dataclasses.asdict`` recurses through the nested dataclasses (params,
    series). ``Mapping[int, float]`` only appears in ``FlowEngineInput``
    (internal, never reaches the DTO) — nothing else needs special handling.
    """
    return _fix_inf(dataclasses.asdict(dto))


def create_app(config: AppConfig | None = None) -> Flask:
    """Build the Flask app. ``config`` carries ``db_path``/``host``/``port``."""
    config = config or AppConfig.load()
    db_path = config.db_path

    app = Flask(__name__)

    @app.get("/")
    def index():
        """Serve the static dashboard front (ST7 §4.1)."""
        return send_file(DASHBOARD_FILE)

    @app.get("/api/forecast")
    def get_forecast():
        """Run the pipeline and return the serialised ``ForecastExportDTO`` (Spec 8)."""
        conn = get_connection(db_path)
        try:
            closes = MonthlyCloseDAO(conn).get_monthly_closes()
            if not closes:
                return jsonify({
                    "error": "NO_DATA",
                    "message": "Base vide — lancer sync.",
                }), 503

            raw = ForecastParamsDAO(conn).load_raw()
            flow_params = FlowParams.model_construct(**raw)
            try:
                dto = ForecastPipeline().run(closes, flow_params)
                payload = dto_to_dict(dto)
                # Last monthly close, exposed for the params-modal label only —
                # NOT the engine's anchor_price (ST8 §3.1, never merge the two).
                last_close = closes[-1]
                payload["params"]["last_close_date"] = last_close.month.strftime("%Y-%m")
                payload["params"]["last_close_price"] = last_close.price
                return jsonify(payload)
            except InsufficientHistoryError as exc:
                return jsonify({
                    "error": "INSUFFICIENT_HISTORY",
                    "message": str(exc),
                }), 503
            except Exception as exc:
                app.logger.error("forecast error: %s", exc, exc_info=True)
                return jsonify({"error": "INTERNAL_ERROR"}), 500
        finally:
            conn.close()

    @app.get("/api/sync-status")
    def get_sync_status():
        """Return ``sync_status`` + metadata (ST7 §4.2).

        ``sync_status`` itself is a live ``SyncOrchestrator.run()`` outcome and
        is NOT persisted (ST7 §3.1: only ``last_sync_date`` lives in
        ``app_meta`` — ``interpolated_months``/``missing_months`` are derived
        by query). Best-effort reconstruction from persisted state: a known
        ``last_sync_date`` means the last sync completed without a blocking
        error ("OK"); its absence — including an empty database — is "UNKNOWN".
        """
        conn = get_connection(db_path)
        try:
            last_sync_date = AppMetaDAO(conn).get_meta("last_sync_date")
            rows = conn.execute(
                "SELECT month FROM monthly_close WHERE origin = 'interpolated' ORDER BY month"
            ).fetchall()
            interpolated_months = [row["month"] for row in rows]
            sync_status = "OK" if last_sync_date is not None else "UNKNOWN"
            return jsonify({
                "sync_status": sync_status,
                "last_sync_date": last_sync_date,
                "interpolated_months": interpolated_months,
                "missing_months": [],
            })
        finally:
            conn.close()

    @app.route("/api/params", methods=["GET", "POST"])
    def params():
        """Read/update the persisted forecast profile (ST7 §4.1)."""
        conn = get_connection(db_path)
        try:
            dao = ForecastParamsDAO(conn)

            if request.method == "GET":
                return jsonify(dao.load_raw())

            body = request.get_json(silent=True)
            if not body:
                return jsonify({"error": "INVALID_JSON"}), 400

            # Cross-field validators need anchor_year/HORIZON in context (ST8 §4.1).
            anchor_year = 2025
            closes = MonthlyCloseDAO(conn).get_monthly_closes()
            if closes:
                try:
                    anchor_year = Aggregator().aggregate(closes).anchor_year
                except Exception:
                    pass

            try:
                flow_params = FlowParams.model_validate(
                    body,
                    context={"anchor_year": anchor_year, "horizon": BEAR_CONSTANTS.HORIZON},
                )
            except ValidationError as exc:
                # include_context=False : ctx.error embarque l'exception Python brute
                # (ValueError des validators), non sérialisable en JSON par jsonify.
                return jsonify({
                    "error": "PARAM_VALIDATION",
                    "detail": exc.errors(include_context=False),
                }), 422

            dao.save(flow_params)
            return jsonify({"status": "ok"})
        finally:
            conn.close()

    return app
