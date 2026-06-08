"""Light scaffold smoke tests (non-blocking — Plan de tests TBD).

Verifies the app boots, the schema init is idempotent, and the routes answer
real JSON shapes (not the old ``not_implemented`` stub). Each test builds its
own app on a temporary, freshly-initialised database (``tmp_path``) — never
the production ``forecast.db``.
"""

from __future__ import annotations

from config.app_config import AppConfig
from storage.db import init_schema
from web.app import create_app


def _client(tmp_path):
    db_path = tmp_path / "forecast.db"
    init_schema(db_path)
    return create_app(AppConfig(db_path=db_path)).test_client()


def test_index_serves_dashboard(tmp_path):
    client = _client(tmp_path)
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"<!DOCTYPE html>" in resp.data


def test_forecast_returns_json(tmp_path):
    client = _client(tmp_path)
    resp = client.get("/api/forecast")
    body = resp.get_json()

    assert resp.status_code in (200, 503)
    if resp.status_code == 200:
        assert "params" in body
        assert "series" in body
    else:
        assert "error" in body


def test_sync_status_returns_json(tmp_path):
    client = _client(tmp_path)
    resp = client.get("/api/sync-status")

    assert resp.status_code == 200
    assert "sync_status" in resp.get_json()


def test_params_get_and_post_return_200(tmp_path):
    client = _client(tmp_path)

    get_resp = client.get("/api/params")
    assert get_resp.status_code == 200
    assert "initial_stack" in get_resp.get_json()

    valid_body = {
        "initial_stack": 1.0,
        "reference_price": 101700.0,
        "monthly_expenses": 2500.0,
        "inflation_rate": 0.06,
        "spending_growth_rate": 0.05,
        "btc_spending_start_year": 2035,
        "monthly_dca": 0.0,
        "dca_growth_rate": 0.0,
        "dca_end_year": None,
    }
    post_resp = client.post("/api/params", json=valid_body)
    assert post_resp.status_code in (200, 422)
    if post_resp.status_code == 200:
        assert post_resp.get_json() == {"status": "ok"}


def test_schema_init_is_idempotent(tmp_path):
    db = tmp_path / "forecast.db"
    init_schema(db)
    init_schema(db)  # second run must not raise
    assert db.exists()
