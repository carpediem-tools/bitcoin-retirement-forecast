"""Bear integrity constants of the price engine (Spec Moteur de prix v1.0 §3.2).

Code constants, adjustable PER RELEASE ONLY — never exposed as a user setting
(Cadrage §4, Bear scenario integrity). Pure declarative module: stdlib only
(math, typing), no logic, no I/O, no dependency on flask/sqlite3/requests/
pydantic/config (CLAUDE.md "Frontière config/ vs domain/").

NOT here by design:
- ``MM_WINDOW_YEARS`` — §3.2 states explicitly it is NOT an engine constant;
  it is centralised in the Aggregation module (the engine only consumes the
  scalar ``mm_anchor``).
- ``midpoint`` (2040.5) and ``k`` — DERIVED values computed later by
  ``price_engine`` from SIGMOID_CALENDAR_ORIGIN, PLATEAU_YEAR and
  SIGMOID_CONSTANT. Never hard-coded.
"""

import math
from typing import Final

# Power-law slope on price (price = a × t^b).
POWER_LAW_EXPONENT: Final[float] = 5.7675

# Time origin t = year − 2008 — fixed calendar rail, never re-anchored.
POWER_LAW_TIME_ORIGIN: Final[int] = 2008

# Factor applied to the base ARR (Bear under-performance, −40%).
BEAR_DISCOUNT: Final[float] = 0.60

# Blend transition span MM → power law (years after the anchor).
BLEND_WINDOW_YEARS: Final[int] = 6

# Asymptotic long-term ARR plateau — frozen.
PLATEAU_ARR: Final[float] = 0.03

# Year at which the plateau is reached — frozen.
PLATEAU_YEAR: Final[int] = 2055

# Sigmoid slope calibration for ~95% transition at PLATEAU_YEAR (= ln(19)).
# Derived from math.log, never a frozen numeric literal.
SIGMOID_CONSTANT: Final[float] = math.log(19.0)

# Calendar origin of the sigmoid midpoint — fixed calendar rail of CONVERGENCE
# (DEC-MOTEUR-01), NOT the projection anchor. The anchor (anchor_year) is
# dynamic; this rail keeps the maturation calendar toward the plateau stable.
SIGMOID_CALENDAR_ORIGIN: Final[int] = 2026

# Projection horizon (upper bound year). Absent from §3.2, carried by CLAUDE.md.
HORIZON: Final[int] = 2072
