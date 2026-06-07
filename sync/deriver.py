"""Monthly-close derivation (Synchro v1.3 §4.2, §4.4, §4.5).

Converts UTC millisecond timestamps to (year, month) keys and keeps the last
point of each closed month. UTC everywhere — never a naive datetime (ST7 §9).
"""

from __future__ import annotations

from datetime import datetime, timezone


class MonthlyCloseDeriver:
    """Derives monthly closes from the raw daily price series."""

    def derive(self, prices: list[list[float]], now: datetime | None = None) -> dict[str, float]:
        """Map ``[[ts_ms, price], ...]`` to ``{'YYYY-MM': close_price}``.

        For each civil-month key, keeps the LAST point received (§4.4 — the
        source order is not assumed). The current, not-yet-closed month is
        dropped (§4.5): with a daily ``days=365`` series it is the only month
        that can ever be open.
        """
        now = now if now is not None else datetime.now(timezone.utc)
        current_key = (now.year, now.month)

        latest_by_month: dict[tuple[int, int], tuple[datetime, float]] = {}
        for timestamp_ms, price in prices:
            # Calendar arithmetic stays in stdlib — no manual day-counting,
            # leap years included (§4.2).
            point_date = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
            key = (point_date.year, point_date.month)
            if key == current_key:
                continue
            seen = latest_by_month.get(key)
            if seen is None or point_date > seen[0]:
                latest_by_month[key] = (point_date, price)

        return {
            f"{year:04d}-{month:02d}": price
            for (year, month), (_, price) in sorted(latest_by_month.items())
        }
