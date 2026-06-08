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


def compute_sync_status(last_close_date: str) -> str:
    """Classify ``last_close_date`` ('YYYY-MM') against the current month (ST7 §4.2).

    "synchronized" when the last close is the previous month (M-1); also
    "synchronized" for M-2 within a 5-day grace window at the start of the
    month (CoinGecko monthly-close lag). Anything else is "stale".
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    year, month = now.year, now.month
    m1_month = month - 1 if month > 1 else 12
    m1_year = year if month > 1 else year - 1
    m2_month = m1_month - 1 if m1_month > 1 else 12
    m2_year = m1_year if m1_month > 1 else m1_year - 1
    expected_m1 = f"{m1_year}-{m1_month:02d}"
    expected_m2 = f"{m2_year}-{m2_month:02d}"
    if last_close_date == expected_m1:
        return "synchronized"
    if last_close_date == expected_m2 and now.day <= 5:
        return "synchronized"
    return "stale"


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
            # reference_price is always overwritten with the last DB monthly close —
            # never a user-editable field (ST8 §3.1: KPI current_portfolio, distinct
            # from the engine's anchor_price). Fallback to the loaded value only if
            # the table is empty (theoretically impossible in production with the seed).
            last_close = MonthlyCloseDAO(conn).get_last_close()
            if last_close is not None:
                raw["reference_price"] = last_close.price
            flow_params = FlowParams.model_construct(**raw)
            try:
                dto = ForecastPipeline().run(closes, flow_params)
                payload = dto_to_dict(dto)
                # Last monthly close, exposed for the params-modal label only —
                # NOT the engine's anchor_price (ST8 §3.1, never merge the two).
                last_close_row = closes[-1]
                last_close_date = last_close_row.month.strftime("%Y-%m")
                payload["params"]["last_close_date"] = last_close_date
                payload["params"]["last_close_price"] = last_close_row.price
                # Sync badge data (ST7 §4.2): classify the last close against the
                # current month, and expose the persisted last sync date (short form).
                last_sync_date = AppMetaDAO(conn).get_meta("last_sync_date")
                payload["params"]["reference_price_sync"] = compute_sync_status(last_close_date)
                payload["params"]["last_sync_date_short"] = (
                    last_sync_date[:10] if last_sync_date is not None else None
                )
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

            # reference_price is no longer a user-editable field (ST8 §3.1):
            # always overwritten with the last DB monthly close, like GET /api/forecast.
            # Fallback to the persisted profile if the table is empty (theoretically
            # impossible in production with the seed).
            last_close = MonthlyCloseDAO(conn).get_last_close()
            if last_close is not None:
                body["reference_price"] = last_close.price
            else:
                body["reference_price"] = dao.load_raw().get("reference_price")

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
