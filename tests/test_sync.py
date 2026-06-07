"""Synchronisation pipeline (Synchro v1.3 / ST7 §8). CoinGecko is ALWAYS mocked
— no real network call. Each class is checked in isolation by composition, plus
end-to-end orchestrator runs against an in-memory SQLite base.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest
import requests

from storage.dao import AppMetaDAO, MonthlyCloseDAO
from storage.db import get_connection, init_schema
from sync.client import BASE_URL_KEYLESS, BASE_URL_PRO, TIMEOUT, CoinGeckoClient
from sync.deriver import MonthlyCloseDeriver
from sync.errors import SyncApiError, SyncGranularityError, SyncStructError
from sync.interpolator import Interpolator
from sync.orchestrator import SyncOrchestrator
from sync.reconciler import Reconciler
from sync.validator import ResponseValidator

# Reference "now" for orchestrator runs: 2026-06-15 -> the 12 most recent
# CLOSED months are June 2025 .. May 2026 (June 2026 is open, excluded).
NOW = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
TODAY = date(2026, 6, 15)
WINDOW = (
    "2025-06", "2025-07", "2025-08", "2025-09", "2025-10", "2025-11",
    "2025-12", "2026-01", "2026-02", "2026-03", "2026-04", "2026-05",
)


def _ts_ms(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp() * 1000)


def _daily_series(end: date, n: int, base: float = 50_000.0, step: float = 10.0):
    """``n`` consecutive daily points (UTC midnight) ending at ``end`` inclusive."""
    return [[_ts_ms(end - timedelta(days=n - 1 - i)), base + step * i] for i in range(n)]


class _FakeResponse:
    def __init__(self, payload, status: int = 200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(str(self.status_code))

    def json(self):
        return self._payload


class _StubClient:
    """Pipeline-level CoinGecko stand-in — returns a fixed payload or raises."""

    def __init__(self, payload=None, error=None):
        self._payload = payload
        self._error = error

    def fetch_market_chart(self, days: int = 365):
        if self._error is not None:
            raise self._error
        return self._payload


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "forecast.db"
    init_schema(db_path)
    connection = get_connection(db_path)
    yield connection
    connection.close()


@pytest.fixture
def dao(conn):
    return MonthlyCloseDAO(conn)


@pytest.fixture
def meta(conn):
    return AppMetaDAO(conn)


def _orchestrator(client, dao, meta):
    return SyncOrchestrator(
        client=client,
        validator=ResponseValidator(),
        deriver=MonthlyCloseDeriver(),
        reconciler=Reconciler(dao),
        interpolator=Interpolator(dao),
        meta_dao=meta,
    )


# ---------------------------------------------------------------------------
# CoinGeckoClient — base URL / headers / mandatory timeout / no-retry mapping
# ---------------------------------------------------------------------------

def test_client_keyless_targets_public_api_with_mandatory_timeout():
    with patch("sync.client.requests.get", return_value=_FakeResponse({"prices": [[1, 2]]})) as get:
        CoinGeckoClient(api_key=None).fetch_market_chart(days=365)

    args, kwargs = get.call_args
    assert args[0] == f"{BASE_URL_KEYLESS}/coins/bitcoin/market_chart"
    assert kwargs["params"] == {"vs_currency": "usd", "days": 365}
    assert kwargs["headers"] is None
    assert kwargs["timeout"] == TIMEOUT == (5, 10)


def test_client_with_key_targets_pro_api_with_demo_header():
    with patch("sync.client.requests.get", return_value=_FakeResponse({"prices": [[1, 2]]})) as get:
        CoinGeckoClient(api_key="secret").fetch_market_chart()

    args, kwargs = get.call_args
    assert args[0] == f"{BASE_URL_PRO}/coins/bitcoin/market_chart"
    assert kwargs["headers"] == {"x-cg-demo-api-key": "secret"}


def test_client_network_failure_maps_to_sync_api_error_no_retry():
    with patch("sync.client.requests.get",
               side_effect=requests.exceptions.ConnectionError("refused")) as get:
        with pytest.raises(SyncApiError) as exc:
            CoinGeckoClient().fetch_market_chart()

    assert exc.value.code == "SYNC_API_ERR"
    assert get.call_count == 1  # no retry (Synchro §4.9)


# ---------------------------------------------------------------------------
# ResponseValidator — blocking (structure, granularity) + non-blocking (volume, freshness)
# ---------------------------------------------------------------------------

def test_validator_rejects_unreadable_structure():
    with pytest.raises(SyncStructError):
        ResponseValidator().validate({"market_caps": []})


def test_validator_rejects_hourly_granularity():
    hourly = [[i * 3_600_000, 50_000.0 + i] for i in range(400)]
    with pytest.raises(SyncGranularityError):
        ResponseValidator().validate({"prices": hourly})


def test_validator_warns_on_volume_and_staleness():
    # 350 points (< 360) ending 5 days before `now` -> both non-blocking warnings.
    series = _daily_series(date(2026, 6, 10), 350)
    warnings = ResponseValidator().validate({"prices": series}, now=NOW)
    assert {w.code for w in warnings} == {"SYNC_VOLUME_WARN", "SYNC_STALE_WARN"}


# ---------------------------------------------------------------------------
# MonthlyCloseDeriver — UTC conversion incl. leap day, last point of closed month
# ---------------------------------------------------------------------------

def test_deriver_keeps_last_point_of_closed_month_utc_including_leap_day():
    now = datetime(2024, 3, 15, tzinfo=timezone.utc)
    prices = [
        [_ts_ms(date(2024, 2, 27)), 100.0],
        [_ts_ms(date(2024, 2, 28)), 101.0],
        [_ts_ms(date(2024, 2, 29)), 102.0],   # leap day -> last close of Feb 2024
        [_ts_ms(date(2024, 3, 1)), 200.0],    # current month -> ignored (§4.5)
        [_ts_ms(date(2024, 3, 10)), 210.0],
    ]
    assert MonthlyCloseDeriver().derive(prices, now=now) == {"2024-02": 102.0}


# ---------------------------------------------------------------------------
# DAO upsert guard + Reconciler (step 1)
# ---------------------------------------------------------------------------

def test_upsert_freezes_existing_real(dao):
    dao.upsert_monthly_close("2025-01", 100.0, "real", "2025-01-01T00:00:00+00:00")
    dao.upsert_monthly_close("2025-01", 999.0, "real", "2025-02-01T00:00:00+00:00")

    close = dao.get_monthly_close("2025-01")
    assert (close.price, close.origin) == (100.0, "real")


def test_upsert_overwrites_interpolated_with_real(dao):
    dao.upsert_monthly_close("2025-01", 100.0, "interpolated", "2025-01-01T00:00:00+00:00")
    dao.upsert_monthly_close("2025-01", 105.0, "real", "2025-02-01T00:00:00+00:00")

    close = dao.get_monthly_close("2025-01")
    assert (close.price, close.origin) == (105.0, "real")


def test_reconciler_writes_only_window_months_present_in_derived(dao):
    Reconciler(dao).reconcile(
        derived={"2025-05": 111.0, "2025-06": 112.0},
        window=["2025-05", "2025-06", "2025-07"],
    )
    assert (dao.get_monthly_close("2025-05").price, dao.get_monthly_close("2025-05").origin) \
        == (111.0, "real")
    assert dao.get_monthly_close("2025-06").price == 112.0
    assert dao.get_monthly_close("2025-07") is None  # left for step 2 (Interpolator)


# ---------------------------------------------------------------------------
# Interpolator (step 2) — linear interpolation, bounded vs unbounded gaps
# ---------------------------------------------------------------------------

def test_interpolator_fills_two_month_gap_bounded_by_real(dao):
    updated = "2025-01-01T00:00:00+00:00"
    dao.upsert_monthly_close("2025-01", 100.0, "real", updated)
    dao.upsert_monthly_close("2025-04", 400.0, "real", updated)

    interpolated, missing = Interpolator(dao).interpolate(
        ["2025-01", "2025-02", "2025-03", "2025-04"]
    )

    assert interpolated == ("2025-02", "2025-03")
    assert missing == ()
    # V_A + (V_B - V_A) * k / N, V_A=100, V_B=400, N=3 (span in months)
    assert dao.get_monthly_close("2025-02").price == pytest.approx(100.0 + 300.0 * 1 / 3)
    assert dao.get_monthly_close("2025-02").origin == "interpolated"
    assert dao.get_monthly_close("2025-03").price == pytest.approx(100.0 + 300.0 * 2 / 3)
    assert dao.get_monthly_close("2025-03").origin == "interpolated"


def test_interpolator_leaves_unbounded_gap_absent_and_reported(dao):
    updated = "2025-01-01T00:00:00+00:00"
    dao.upsert_monthly_close("2025-01", 100.0, "real", updated)
    # 2025-02..2025-04 absent; no `real` bound on the right -> not interpolable.

    interpolated, missing = Interpolator(dao).interpolate(
        ["2025-01", "2025-02", "2025-03", "2025-04"]
    )

    assert interpolated == ()
    assert missing == ("2025-02", "2025-03", "2025-04")
    assert dao.get_monthly_close("2025-02") is None


# ---------------------------------------------------------------------------
# SyncOrchestrator — end-to-end pipeline runs
# ---------------------------------------------------------------------------

def test_orchestrator_nominal_ok_writes_real_closes_for_the_window(conn, dao, meta):
    prices = _daily_series(TODAY, 365)  # volume in range, freshest point = today (age 0)
    orchestrator = _orchestrator(_StubClient(payload={"prices": prices}), dao, meta)

    result = orchestrator.run(now=NOW)

    assert result.sync_status == "OK"
    assert result.last_sync_date == NOW.isoformat()
    assert meta.get_meta("last_sync_date") == NOW.isoformat()

    expected = MonthlyCloseDeriver().derive(prices, now=NOW)
    assert set(expected) >= set(WINDOW)
    for month in WINDOW:
        close = dao.get_monthly_close(month)
        assert close is not None
        assert close.origin == "real"
        assert close.price == pytest.approx(expected[month])


def test_orchestrator_degraded_api_keeps_base_and_still_interpolates(conn, dao, meta):
    seed = "2020-01-01T00:00:00+00:00"
    # A bounded 1-month gap inside the window: 2025-07 absent between two `real`.
    dao.upsert_monthly_close("2025-06", 100.0, "real", seed)
    dao.upsert_monthly_close("2025-08", 120.0, "real", seed)
    dao.upsert_monthly_close("2025-09", 999.0, "real", seed)
    meta.set_meta("last_sync_date", "2026-05-01T00:00:00+00:00")

    orchestrator = _orchestrator(_StubClient(error=SyncApiError("network down")), dao, meta)
    result = orchestrator.run(now=NOW)

    assert result.sync_status == "DEGRADED_API"
    # The previously stored date is reported back — NOT overwritten on failure.
    assert result.last_sync_date == "2026-05-01T00:00:00+00:00"
    assert meta.get_meta("last_sync_date") == "2026-05-01T00:00:00+00:00"

    # Existing `real` values are untouched (base preserved).
    assert dao.get_monthly_close("2025-06").price == 100.0
    assert dao.get_monthly_close("2025-09").price == 999.0

    # Step 2 still ran on the bounded gap (§4.9: applies even in degraded mode).
    assert result.interpolated_months == ("2025-07",)
    gap = dao.get_monthly_close("2025-07")
    assert gap.origin == "interpolated"
    assert gap.price == pytest.approx(100.0 + (120.0 - 100.0) * 1 / 2)


def test_orchestrator_degraded_granularity_keeps_base(conn, dao, meta):
    dao.upsert_monthly_close("2025-06", 100.0, "real", "2020-01-01T00:00:00+00:00")
    hourly = [[i * 3_600_000, 50_000.0 + i] for i in range(400)]

    orchestrator = _orchestrator(_StubClient(payload={"prices": hourly}), dao, meta)
    result = orchestrator.run(now=NOW)

    assert result.sync_status == "DEGRADED_GRANULARITY"
    assert dao.get_monthly_close("2025-06").price == 100.0
