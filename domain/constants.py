"""Bear integrity constants of the price engine (Spec technique 8 §3.1).

Code constants, adjustable PER RELEASE ONLY — never exposed as a user setting
(Cadrage §4, Bear scenario integrity). Pure declarative module: stdlib only
(dataclasses, math), no logic, no I/O, no dependency on flask/sqlite3/requests/
pydantic/config (CLAUDE.md "Frontière config/ vs domain/").

NOT here by design:
- ``MM_WINDOW_YEARS`` — §3.1, Figure 2 and §1 place it in the Aggregation
  module (``domain/aggregation.py``); the engine only consumes the scalar
  ``mm_anchor``. Never an attribute of ``BearConstants``.
- ``midpoint`` (2040.5) and ``k`` — DERIVED values computed later by
  ``price_engine`` from SIGMOID_CALENDAR_ORIGIN, PLATEAU_YEAR and
  SIGMOID_CONSTANT. Never hard-coded.
"""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class BearConstants:
    # Power-law slope on price (price = a × t^b).
    POWER_LAW_EXPONENT: float = 5.7675
    # Time origin t = year − 2008 — fixed calendar rail, never re-anchored.
    POWER_LAW_TIME_ORIGIN: int = 2008
    # Factor applied to the base ARR (Bear under-performance, −40%).
    BEAR_DISCOUNT: float = 0.60
    # Blend transition span MM → power law (years after the anchor).
    BLEND_WINDOW_YEARS: int = 6
    # Asymptotic long-term ARR plateau — frozen.
    PLATEAU_ARR: float = 0.03
    # Year at which the plateau is reached — frozen.
    PLATEAU_YEAR: int = 2055
    # Sigmoid slope calibration for ~95% transition at PLATEAU_YEAR (= ln(19)).
    # Derived from math.log, never a frozen numeric literal.
    SIGMOID_CONSTANT: float = math.log(19.0)
    # Calendar origin of the sigmoid midpoint — fixed calendar rail of
    # CONVERGENCE (DEC-MOTEUR-01), NOT the projection anchor.
    SIGMOID_CALENDAR_ORIGIN: int = 2026
    # Projection horizon (upper bound year). Config-rewidenable to 2100 [V2].
    HORIZON: int = 2072


# Default immutable instance, consumed by price_engine and the tests.
BEAR_CONSTANTS: BearConstants = BearConstants()
