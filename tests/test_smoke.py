"""Light scaffold smoke tests (non-blocking — Plan de tests TBD).

Verifies the app boots, the schema init is idempotent, and stub routes answer.
"""

from __future__ import annotations

from storage.db import init_schema
from web.app import create_app


def test_index_serves_dashboard():
    client = create_app().test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"<!DOCTYPE html>" in resp.data


def test_forecast_stub_returns_200():
    client = create_app().test_client()
    resp = client.get("/api/forecast")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "not_implemented"}


def test_sync_status_stub_returns_200():
    client = create_app().test_client()
    resp = client.get("/api/sync-status")
    assert resp.status_code == 200


def test_params_get_and_post_return_200():
    client = create_app().test_client()
    assert client.get("/api/params").status_code == 200
    assert client.post("/api/params", json={}).status_code == 200


def test_schema_init_is_idempotent(tmp_path):
    db = tmp_path / "forecast.db"
    init_schema(db)
    init_schema(db)  # second run must not raise
    assert db.exists()
