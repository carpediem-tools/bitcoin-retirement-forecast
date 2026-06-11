# Bitcoin Retirement Forecast

## Project
**Local-web** Python application: maintains a SQLite database of monthly BTC/USD closes (since 2010), syncs on launch via **keyless** CoinGecko, and projects the viability of a BTC retirement (**Bear** scenario, drawdown + optional DCA) through 2072. Rebuild of an existing spreadsheet model. GitHub repo, **MIT** license.

## Stack
- **Python 3.13**
- **Flask** (routes) + **waitress** (WSGI server — NEVER the Flask dev server, even locally)
- **SQLite** (persisted monthly closes)
- **requests** (CoinGecko; `timeout=(5, 10)` **required**)
- **Pydantic** (validation of user flow parameters)
- **webbrowser** (stdlib; opens the tab on startup, **after** waitress is listening)
- **python-dotenv** (*optional* reading of a CoinGecko key; never required)
- Frontend: `btc_dashboard.html` (Chart.js) — wired onto `/api/forecast`, fully translated to EN

## Commands
- Launch: `python run.py` → waitress on `127.0.0.1:8000` (**incremental fallback bind** 8001, 8002… if busy) → opens a browser tab
- Tests: `pytest tests/ -v`
- Network binding: `127.0.0.1` **only**, never `0.0.0.0` (single-user, no auth)
- **Historical seed**: `data/seed_monthly_closes.csv` (Coin Metrics Community Data,
  CC license, 191 months 2010-07→2026-05). Loaded on startup by
  `storage.db.seed_from_csv()` (INSERT OR IGNORE — real frozen). Regenerable:
  `python scripts/generate_seed.py`. Attribution required (already in README).

## Architecture — layers and allowed dependencies
- `domain/` — **pure business logic, no I/O or state**: `aggregation` → `price_engine` → `flow_engine` → `pipeline` → `assemble_dto`. Testable by **composition** (engine on REF, flow on Subsidy). All submodules are **packages** (`__init__.py`): `price_engine/`, `aggregation/`, `flow_engine/`, `pipeline/`.
- `domain/aggregation/` is a **package** (like `price_engine/`), not a flat-file module.
- `domain/errors.py`: DomainError (base) + InsufficientHistoryError (code=INSUFFICIENT_HISTORY).
- `sync/errors.py`: SyncError, SyncApiError, SyncStructError, SyncGranularityError.
- `sync/` — keyless CoinGecko client, close derivation, reconciliation + interpolation, `DEGRADED_*` states.
- HTTP layer (Flask) — `GET`/`POST /api/params`, `GET /api/forecast` (serializes `ForecastExportDTO`).
- Data layer — SQLite (read/write monthly closes).
- **Dependency rule:** `domain/` depends on **nothing** (no Flask, no SQLite, no requests). External layers depend on `domain/`, never the reverse.
  **Documented exception (ST8 §3.4):** `domain/flow_engine/__init__.py` imports `FlowParams` from `config/params.py` — `FlowEngineInput` is defined in this package (≠ `domain/models.py`) to avoid the `domain → config` circularity. The only `domain → config` contact point allowed.
- **Language:** code / fields / routes / logs / UI labels in **English**; spec prose and exchanges in **French**.
- **Direction of dependencies**: `domain/` is pure (no import of `storage/`, `sync/`, `web/`,
  `requests`, `flask`, `sqlite3`). `storage/` MAY import `domain.models` (boundary types
  only). `sync/` imports `storage/` and `domain.models`. Never the reverse.
  (Incorrect phrasing to avoid in briefs: "storage/ does not import domain/" —
  the constraint runs the other way.)

## Invariants web layer
- `reference_price` is no longer a user parameter. It is always
  injected from `MonthlyCloseDAO.get_last_close().price` in web/app.py,
  on both GET /api/forecast and POST /api/params, before pipeline
  execution. Never let Pydantic receive it from the frontend.
- buildTable(hist, proj, params): takes params as a 3rd argument since the 10/06 session — never call without params
- currentAnchorYear: module-level variable in btc_dashboard.html, populated by buildDashboard — the only source of anchor_year accessible in openParamsModal


## Critical invariants — NEVER BREAK
- **Engine non-regression (gate for any merge touching `price_engine`)**: `anchor_year=2025, anchor_price=101700, mm_anchor=0.361334851227728` → `nominal_price(2026..2072)` = `L37..L83` of the pilot **to the cent** (relative guard `1e-9`). ⚠️ `mm_anchor` MUST be the full-precision pilot value (`Forecast Bear!C12`); `0.3613` is a 4-decimal display rounding (gap ~3.5e-5 ≫ 1e-9) that breaks the 5 blend years. Checks: `arr_theo(2026)=0.210231258`, `nominal(2026)=123080.52`, `nominal(2072)≈2373743`.
- **Prices and rates as `float` (IEEE-754 double).**
- **SOLE inter-referential join**: `nominal_price` (engine → flow). Nothing else crosses.
- **Counter `C = year − anchor_year`**: `C=0` at the anchor, `C=1` at the 1st projection. **Flow side only** (anti-bug V4). The engine indexes by absolute calendar year, never a counter.
- **`anchor_price` (rolling average, capitalization seed) ≠ `reference_price` (KPI `current_portfolio`)** — never merge.
- **Bear integrity constants** (never a user setting; adjustable per release): `POWER_LAW_EXPONENT=5.7675`, `POWER_LAW_TIME_ORIGIN=2008`, `BEAR_DISCOUNT=0.60`, `BLEND_WINDOW_YEARS=6`, `PLATEAU_ARR=0.03`, `PLATEAU_YEAR=2055`, `SIGMOID_CALENDAR_ORIGIN=2026` (fixed), `HORIZON=2072`. **`MM_WINDOW_YEARS=4` centralized in `Aggregator`** (≠ `BLEND_WINDOW_YEARS`, two distinct constants).
- **`SIGMOID_CALENDAR_ORIGIN=2026` is a calendar rail for _convergence_, NOT the origin of the projection.** The origin of the projection is the **anchor** (`anchor_year`/`anchor_price`), which is already dynamic (last real observed point; projection starting at `anchor_year + 1`). This constant only sets the **maturation calendar** of the ARR toward the plateau. It remains **fixed by design** (DEC-MOTEUR-01): a late launch must produce a _lower_ starting ARR (BTC has matured on the real calendar), not reset its maturity. Making it dynamic (`= anchor_year`) would compress the sigmoid (a "cliff" effect on late launches) and cause a **division by zero post-2054**. The **midpoint `= (SIGMOID_CALENDAR_ORIGIN + PLATEAU_YEAR)/2 = 2040.5` is ALWAYS derived, never hardcoded** (see Moteur de prix v1.0 §4.5).
- **`cdv_train` composes inflation AND lifestyle** (DEC-DCA-03): `cdv_train = cdv_inflation × (1+spending_growth)^C`.
- **`mm_anchor`**: MM4 in production (`MM_WINDOW_YEARS=4`); the non-regression vector uses the frozen pilot value (`0.361334851227728`, full precision — not the `0.3613` rounding).
- **`keyless` = standard nominal mode ≠ `DEGRADED_*` states** (sync failure). Do not wire keyless → DEGRADED.
- **Serialization `runway = ∞` → `"Infinity"`** (portable JSON string).
- **Pydantic ValidationError → JSON 422**: always `exc.errors(include_context=False)`
  — `include_context=True` (default) exposes Python `ValueError`s that are not JSON-serializable.
- **% fields in FlowParams** (`inflation_rate`, `spending_growth_rate`, `dca_growth_rate`):
  stored as decimals (0.06 = 6%), converted ×100 for UI display and ÷100 on input.
  Never store or send as a whole-number percentage.
- **Boundary `config/` vs `domain/`:** the **Bear integrity constants** live in `domain/constants.py` (business logic, pure module). `config/` carries the **application config** (loopback host, port, db path) and the **Pydantic validation of USER flow parameters** only. NEVER place integrity constants in `config/` (preserves the purity of `domain/` and the isolation of the non-regression test). waitress port **fixed at 8000** (incremental fallback bind retained).

## Specifications — source of truth (read on demand in `docs/specs/`)
Cadrage v2.1 · Synchronisation v1.3 · Agrégation **v1.3** · Flux v1.1 · Moteur de prix v1.0 · Plan de tests v1.0 · Spec technique 7 (Infra) v1.1 · Spec technique 8 (Moteur de calcul) v1.0.
> When in doubt about a formula or rule: **the spec is authoritative, not memory**. Spec technique 8 covers the `domain/` pipeline and the DTO schema; Spec technique 7 covers infra, HTTP transport, and sync.

## Glossary
- **anchor / ancre**: last real point from which the projection starts (`anchor_year`, `anchor_price`).
- **mm_anchor**: average of the last `MM_WINDOW_YEARS` annual ARRs (MM4 in prod, `MM_WINDOW_YEARS=4`); blend anchor.
- **runway**: number of years before the stack is depleted (`∞` if never depleted).
- **DTO**: `ForecastExportDTO`, semantic JSON mirror of the pilot's `_Export` sheet.

## Commit conventions (MODE_GIT)
`feat:` · `fix:` · `refactor:` · `test:` · `docs:` · `chore:`
