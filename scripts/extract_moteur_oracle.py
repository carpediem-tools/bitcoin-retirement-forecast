"""Extract the price-engine non-regression oracle from the pilot .ods.

Reads ``tests/oracle_sources/forecast_bear_final.ods`` and writes the frozen,
versioned fixture ``tests/fixtures/moteur_pointfixe.json`` (Plan de tests v1.0
§5/§6, TF1 / MOT-NR-*).

For each projected year 2026..2072 it extracts:
  - column K (index 10) -> theoretical ARR  (rows K37:K83)
  - column L (index 11) -> capitalised nominal price (rows L37:L83)
The anchor 2025 sits at spreadsheet row 35 (L35 == 101700).

Before writing, four anchoring controls are asserted; on any failure the script
raises and writes NOTHING (ultimate guard against a silent row/column shift —
odfpy quirks: read the computed ``office:value`` not the formula, and accumulate
``number-rows-repeated`` / ``number-columns-repeated``).

Usage:
    python scripts/extract_moteur_oracle.py
    python scripts/extract_moteur_oracle.py --source PATH --output PATH
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from odf.opendocument import load
from odf.table import Table, TableRow, TableCell

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = PROJECT_ROOT / "tests" / "oracle_sources" / "forecast_bear_final.ods"
DEFAULT_OUTPUT = PROJECT_ROOT / "tests" / "fixtures" / "moteur_pointfixe.json"

# Fixed injection (the pilot's own inputs, re-injected as scalars) — §2.1.
# mm_anchor is the pilot's FULL-PRECISION MM4 anchor (Forecast Bear!C12 /
# _Export!R1C17). The documented "0.3613" (CLAUDE.md, spec) is a 4-decimal
# display rounding — using it breaks the 1e-9 gate on the blend years
# (2026..2030, the only place mm_anchor enters). Keep full precision here.
INJECTION = {"anchor_year": 2025, "anchor_price": 101700, "mm_anchor": 0.361334851227728}

# Spreadsheet geometry (1-based rows, 0-based grid columns).
COL_ARR = 10          # column K
COL_NOMINAL = 11      # column L
ROW_ANCHOR = 35       # L35 == anchor_price (2025)
ROW_FIRST = 37        # K37/L37 == year 2026
YEAR_FIRST = 2026
YEAR_LAST = 2072
EXPECTED_POINTS = YEAR_LAST - YEAR_FIRST + 1  # 47

# Caps so trailing repeated empty rows/cols don't explode the grid.
MAX_ROWS = 200
MAX_COLS = 40

# Anchoring controls (Plan de tests §2.1 / brief).
CTRL_NOMINAL_2026 = 123080.52
CTRL_NOMINAL_2072 = 2373743
CTRL_ARR_2026 = 0.210231258


def _cell_value(cell: TableCell) -> float | None:
    """Return the computed numeric value of a cell, or None if not numeric.

    Uses the office:value attribute (the COMPUTED value, never the formula).
    """
    value_type = cell.getAttribute("valuetype")  # office:value-type
    if value_type in ("float", "percentage", "currency"):
        raw = cell.getAttribute("value")  # office:value
        return float(raw) if raw is not None else None
    return None


def _table_to_grid(table: Table) -> list[list[float | None]]:
    """Materialise a table into a row-major grid, honouring repeat counts."""
    grid: list[list[float | None]] = []
    for row in table.getElementsByType(TableRow):
        if len(grid) >= MAX_ROWS:
            break
        row_rep = int(row.getAttribute("numberrowsrepeated") or 1)
        row_rep = min(row_rep, MAX_ROWS - len(grid))
        cells: list[float | None] = []
        for cell in row.getElementsByType(TableCell):
            if len(cells) >= MAX_COLS:
                break
            col_rep = int(cell.getAttribute("numbercolumnsrepeated") or 1)
            col_rep = min(col_rep, MAX_COLS - len(cells))
            cells.extend([_cell_value(cell)] * col_rep)
        for _ in range(row_rep):
            grid.append(list(cells))
    return grid


def _grid_get(grid: list[list[float | None]], row_1based: int, col_0based: int) -> float | None:
    idx = row_1based - 1
    if 0 <= idx < len(grid) and col_0based < len(grid[idx]):
        return grid[idx][col_0based]
    return None


def _select_sheet(doc) -> list[list[float | None]]:
    """Pick the sheet whose L35 matches the anchor price (101700).

    Robust to sheet naming; the control asserts remain the ultimate guard.
    """
    tables = doc.getElementsByType(Table)
    if not tables:
        raise ValueError("No sheet found in the .ods document.")
    for table in tables:
        grid = _table_to_grid(table)
        anchor = _grid_get(grid, ROW_ANCHOR, COL_NOMINAL)
        if anchor is not None and round(anchor, 2) == float(INJECTION["anchor_price"]):
            return grid
    # Fall back to the first sheet so the asserts produce a clear failure.
    return _table_to_grid(tables[0])


def extract(source: Path) -> list[dict]:
    """Extract the 2026..2072 oracle rows from the pilot .ods."""
    doc = load(str(source))
    grid = _select_sheet(doc)
    oracle: list[dict] = []
    for year in range(YEAR_FIRST, YEAR_LAST + 1):
        row = ROW_FIRST + (year - YEAR_FIRST)
        arr = _grid_get(grid, row, COL_ARR)
        nominal = _grid_get(grid, row, COL_NOMINAL)
        if arr is None or nominal is None:
            raise ValueError(
                f"Missing value at year {year} (row {row}): "
                f"arr={arr!r}, nominal={nominal!r} — possible row/column shift."
            )
        oracle.append({"year": year, "arr_theo": arr, "nominal_price": nominal})
    return oracle


def _by_year(oracle: list[dict]) -> dict[int, dict]:
    return {row["year"]: row for row in oracle}


def assert_controls(oracle: list[dict]) -> None:
    """Assert the four anchoring controls; raise (no write) on any mismatch."""
    n = len(oracle)
    if n != EXPECTED_POINTS:
        raise AssertionError(f"Expected {EXPECTED_POINTS} points, got {n}.")

    rows = _by_year(oracle)
    nominal_2026 = rows[2026]["nominal_price"]
    nominal_2072 = rows[2072]["nominal_price"]
    arr_2026 = rows[2026]["arr_theo"]

    if round(nominal_2026, 2) != CTRL_NOMINAL_2026:
        raise AssertionError(
            f"nominal_price(2026)={nominal_2026!r} != {CTRL_NOMINAL_2026} (at the cent)."
        )
    if round(nominal_2072) != CTRL_NOMINAL_2072:
        raise AssertionError(
            f"round(nominal_price(2072))={round(nominal_2072)} != {CTRL_NOMINAL_2072}."
        )
    if abs(arr_2026 - CTRL_ARR_2026) >= 1e-9:
        raise AssertionError(
            f"arr_theo(2026)={arr_2026!r} != {CTRL_ARR_2026} (|Δ| >= 1e-9)."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if not args.source.exists():
        raise SystemExit(
            f"Pilot source not found: {args.source}\n"
            "Place forecast_bear_final.ods under tests/oracle_sources/ and re-run."
        )

    oracle = extract(args.source)
    assert_controls(oracle)  # raises before any write on mismatch

    payload = {"injection": INJECTION, "oracle": oracle}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    rows = _by_year(oracle)
    print(f"Controls OK — wrote {len(oracle)} points to {args.output}")
    print(f"  nominal_price(2026) = {rows[2026]['nominal_price']}")
    print(f"  nominal_price(2072) = {rows[2072]['nominal_price']}")
    print(f"  arr_theo(2026)      = {rows[2026]['arr_theo']}")


if __name__ == "__main__":
    main()
