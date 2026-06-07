"""Bear price engine (Spec technique 8 §2.2, Moteur de prix v1.0 §4).

Composition order: power law → blend → discount → sigmoid → floor (Moteur §4.6).
All private methods take the ABSOLUTE calendar year — no counter ``C`` on the
price side (anti-bug V4 guard, Moteur §4.1). The engine indexes by absolute
year; only the Flow side derives ``C = year − anchor_year``.

Pure stage: stdlib (math) + domain.constants + domain.models. Nothing external.
"""

from math import exp

from domain.constants import BEAR_CONSTANTS, BearConstants
from domain.models import AggregationResult, PriceEngineResult, ProjectedYear


class PriceEngine:
    """Projects nominal BTC/USD prices from an AggregationResult anchor.

    Reads the Bear integrity constants from the injected ``BearConstants``
    instance (Figure 2: "PriceEngine reads BearConstants").
    """

    def __init__(self, constants: BearConstants = BEAR_CONSTANTS):
        self._c = constants

    # — §4.5: derived calendar rails, never hard-coded (midpoint=2040.5, k=ln19/14.5) —
    @property
    def sigmoid_midpoint(self) -> float:
        """Sigmoid midpoint = (SIGMOID_CALENDAR_ORIGIN + PLATEAU_YEAR) / 2."""
        return (self._c.SIGMOID_CALENDAR_ORIGIN + self._c.PLATEAU_YEAR) / 2

    @property
    def sigmoid_k(self) -> float:
        """Sigmoid slope k = SIGMOID_CONSTANT / (PLATEAU_YEAR − midpoint)."""
        return self._c.SIGMOID_CONSTANT / (self._c.PLATEAU_YEAR - self.sigmoid_midpoint)

    # — §4.2: power-law ARR —
    def arr_pl(self, year: int) -> float:
        t = year - self._c.POWER_LAW_TIME_ORIGIN          # 2008, fixed calendar rail
        return (t / (t - 1)) ** self._c.POWER_LAW_EXPONENT - 1

    # — §4.3: blend weight, re-anchored on anchor_year —
    def alpha(self, year: int, anchor_year: int) -> float:
        return max(0.0, 1 - (year - anchor_year) / self._c.BLEND_WINDOW_YEARS)

    # — §4.5: sigmoid (midpoint & k derived above) —
    def sigmoid(self, year: int) -> float:
        return 1 / (1 + exp(-self.sigmoid_k * (year - self.sigmoid_midpoint)))

    # — §4.6: assembly + floor —
    def arr_theo(self, year: int, anchor_year: int, mm_anchor: float) -> float:
        a = self.alpha(year, anchor_year)
        base = a * mm_anchor + (1 - a) * self.arr_pl(year)
        disc = base * self._c.BEAR_DISCOUNT                # × 0.60
        s = self.sigmoid(year)
        return max(disc * (1 - s) + self._c.PLATEAU_ARR * s, self._c.PLATEAU_ARR)

    # — §4.7: capitalisation —
    def project(self, agg: AggregationResult) -> PriceEngineResult:
        anchor_year = agg.anchor_year
        anchor_price = agg.anchor_price
        mm_anchor = agg.mm_anchor

        series = [ProjectedYear(anchor_year, None, anchor_price)]
        for year in range(anchor_year + 1, self._c.HORIZON + 1):
            arr = self.arr_theo(year, anchor_year, mm_anchor)
            nominal = series[-1].nominal_price * (1 + arr)
            series.append(ProjectedYear(year, arr, nominal))

        return PriceEngineResult(anchor_year, anchor_price, tuple(series))
