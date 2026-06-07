"""TF1 — engine non-regression gate (Plan de tests v1.0 §2.1 MOT-NR-001..004).

Reproduces the fixed-point oracle ``moteur_pointfixe.json`` (K37:K83 / L37:L83 of
the pilot) at the plan §6 tolerances: prices rounded to the cent then exact
equality, doubled by a relative 1e-9 diagnostic guard; ARR relative ≤ 1e-9.
"""

import json
import math
from datetime import date
from pathlib import Path

from domain.models import AggregationResult
from domain.price_engine import PriceEngine

_ORACLE = json.loads(
    (Path(__file__).parent / "fixtures" / "moteur_pointfixe.json").read_text()
)


def assert_usd_cent(computed: float, oracle: float):
    # Plan §6: round to cent + exact equality, doubled by a 1e-9 relative guard.
    assert round(computed, 2) == round(oracle, 2)
    assert abs(computed - oracle) / abs(oracle) <= 1e-9


def assert_rel(computed: float, oracle: float):
    # Plan §6: rates (ARR) — relative tolerance ≤ 1e-9.
    assert abs(computed - oracle) / abs(oracle) <= 1e-9


def _injection() -> AggregationResult:
    # anchor_year/anchor_price/mm_anchor are the only fields project() consumes;
    # diagnostic fields carry neutral, non-read values.
    inj = _ORACLE["injection"]
    return AggregationResult(
        anchor_year=inj["anchor_year"],
        anchor_price=float(inj["anchor_price"]),
        mm_anchor=inj["mm_anchor"],
        rolling_annual_avg=float(inj["anchor_price"]),
        arr_series=(),
        mm_window_start=date(2019, 1, 1),
        annual_history=(),
    )


def _series_by_year():
    result = PriceEngine().project(_injection())
    return {p.year: p for p in result.series}


def test_mot_nr_003_anchor():
    series = PriceEngine().project(_injection()).series
    anchor = series[0]
    assert anchor.year == 2025
    assert anchor.arr_theo is None
    assert anchor.nominal_price == 101700.0


def test_mot_nr_001_arr_theo():
    by_year = _series_by_year()
    count = 0
    for row in _ORACLE["oracle"]:
        assert_rel(by_year[row["year"]].arr_theo, row["arr_theo"])
        count += 1
    assert count == 47


def test_mot_nr_002_nominal_price():
    by_year = _series_by_year()
    count = 0
    for row in _ORACLE["oracle"]:
        assert_usd_cent(by_year[row["year"]].nominal_price, row["nominal_price"])
        count += 1
    assert count == 47


def test_mot_nr_004_sigmoid_diagnostics():
    engine = PriceEngine()
    assert engine.sigmoid_midpoint == 2040.5
    assert engine.sigmoid_k == math.log(19) / 14.5
