"""Anti-tamper guard on the Bear integrity constants (Moteur de prix v1.0 §3.2).

These values govern the at-the-cent non-regression test, so any accidental
change must fail loudly here.
"""

import math

from domain import constants


def test_power_law_exponent():
    assert constants.POWER_LAW_EXPONENT == 5.7675


def test_power_law_time_origin():
    assert constants.POWER_LAW_TIME_ORIGIN == 2008


def test_bear_discount():
    assert constants.BEAR_DISCOUNT == 0.60


def test_blend_window_years():
    assert constants.BLEND_WINDOW_YEARS == 6


def test_plateau_arr():
    assert constants.PLATEAU_ARR == 0.03


def test_plateau_year():
    assert constants.PLATEAU_YEAR == 2055


def test_sigmoid_constant_is_ln_19():
    assert constants.SIGMOID_CONSTANT == math.log(19.0)


def test_sigmoid_calendar_origin():
    assert constants.SIGMOID_CALENDAR_ORIGIN == 2026


def test_horizon():
    assert constants.HORIZON == 2072


def test_mm_window_years_absent():
    # §3.2: MM_WINDOW_YEARS belongs to Aggregation, never to the engine module.
    assert not hasattr(constants, "MM_WINDOW_YEARS")


def test_derived_values_absent():
    # midpoint and k are derived later by price_engine, never hard-coded here.
    assert not hasattr(constants, "midpoint")
    assert not hasattr(constants, "k")
