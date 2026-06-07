"""Anti-tamper guard on the Bear integrity constants (Spec technique 8 §3.1).

These values govern the at-the-cent non-regression test, so any accidental
change must fail loudly here. The constants now live on the frozen
``BearConstants`` dataclass.
"""

import dataclasses
import math

import pytest

from domain.constants import BEAR_CONSTANTS, BearConstants


def test_power_law_exponent():
    assert BearConstants().POWER_LAW_EXPONENT == 5.7675


def test_power_law_time_origin():
    assert BearConstants().POWER_LAW_TIME_ORIGIN == 2008


def test_bear_discount():
    assert BearConstants().BEAR_DISCOUNT == 0.60


def test_blend_window_years():
    assert BearConstants().BLEND_WINDOW_YEARS == 6


def test_plateau_arr():
    assert BearConstants().PLATEAU_ARR == 0.03


def test_plateau_year():
    assert BearConstants().PLATEAU_YEAR == 2055


def test_sigmoid_constant_is_ln_19():
    assert BearConstants().SIGMOID_CONSTANT == math.log(19.0)


def test_sigmoid_calendar_origin():
    assert BearConstants().SIGMOID_CALENDAR_ORIGIN == 2026


def test_horizon():
    assert BearConstants().HORIZON == 2072


def test_default_instance_matches_class():
    # The exposed default instance is a plain BearConstants() with defaults.
    assert BEAR_CONSTANTS == BearConstants()


def test_mm_window_years_absent():
    # §3.1: MM_WINDOW_YEARS belongs to Aggregation, never to the engine.
    assert not hasattr(BearConstants(), "MM_WINDOW_YEARS")


def test_derived_values_absent():
    # midpoint and k are derived later by price_engine, never hard-coded here.
    assert not hasattr(BearConstants(), "midpoint")
    assert not hasattr(BearConstants(), "k")


def test_instance_is_frozen():
    # Mutating a field must fail loudly (anti-tamper).
    with pytest.raises(dataclasses.FrozenInstanceError):
        BEAR_CONSTANTS.PLATEAU_ARR = 0.05
