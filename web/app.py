"""Flask application factory and routes (ST7 §4.1).

Routes are scaffold stubs returning an explicit ``not_implemented`` placeholder;
business wiring (sync, domain pipeline, DTO) is out of scope here.
"""

from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, request, send_file

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_FILE = PROJECT_ROOT / "btc_dashboard.html"

_NOT_IMPLEMENTED = {"status": "not_implemented"}


def create_app(config: object | None = None) -> Flask:
    """Build the Flask app. ``config`` is accepted for future wiring."""
    app = Flask(__name__)

    @app.get("/")
    def index():
        """Serve the static dashboard front (ST7 §4.1)."""
        return send_file(DASHBOARD_FILE)

    @app.get("/api/forecast")
    def get_forecast():
        """Return the ForecastExportDTO (Spec 8). Stub for now."""
        return jsonify(_NOT_IMPLEMENTED), 200

    @app.get("/api/sync-status")
    def get_sync_status():
        """Return sync_status + metadata (ST7 §4.2). Stub for now."""
        return jsonify(_NOT_IMPLEMENTED), 200

    @app.route("/api/params", methods=["GET", "POST"])
    def params():
        """Read/update the persisted forecast profile (ST7 §4.1). Stub for now."""
        _ = request.get_json(silent=True) if request.method == "POST" else None
        return jsonify(_NOT_IMPLEMENTED), 200

    return app
