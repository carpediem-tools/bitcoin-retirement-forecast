# Bitcoin Retirement Forecast

A local Python web app projecting a BTC retirement stack through 2072 under a conservative Bear scenario.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Overview

Bitcoin Retirement Forecast is a single-user dashboard that models whether a
Bitcoin stack can sustain a retirement over the long term, under a
deliberately conservative ("Bear") price scenario. The projection runs from
the present through 2072, combining a power-law price model anchored on a
4-year moving average of recent annual returns with optional DCA
accumulation and drawdown spending. The output includes an estimated
retirement *runway* — the number of years before the stack would be
exhausted, if ever. The dashboard also shows the available historical price
record back to 2010 alongside the projection, so recent reality and the
projected trajectory can be read side by side.

---

## Features

- Bear price model: power-law decay with sigmoid convergence to a long-term
  ARR plateau
- MM4 anchor: projection seeded from a 4-year moving average of historical
  annual returns
- Monthly BTC/USD price sync via the CoinGecko public API (keyless)
- Historical price seed (2010-07 onward) from Coin Metrics Community Data
- Interactive dashboard: KPIs, charts, and a full year-by-year data table
- Configurable simulation parameters (stack, expenses, inflation, DCA, ...)
- Runs entirely locally — no accounts, no Docker, no cloud dependency

---

## Prerequisites

- Python 3.13+
- pip

Nothing else is required: data is stored in a local SQLite database, and the
app serves itself as a local web server.

---

## Quick start

```bash
git clone https://github.com/carpediem-tools/bitcoin-retirement-forecast
cd bitcoin-retirement-forecast
pip install -r requirements.txt
python run.py
```

The app opens automatically at http://127.0.0.1:8000.

---

## First run

On first launch, the app creates a local SQLite database and loads it with
the historical price seed (2010-07 → 2026-05, from Coin Metrics). It then
syncs the most recent monthly closes from CoinGecko, after which the
dashboard is ready immediately. The sync badge in the header reflects the
freshness of the stored price history ("Sync OK" / "Sync KO"); if a sync
attempt fails, the app continues to run on the data already stored locally.
On subsequent launches, only the CoinGecko sync step runs — the historical
seed is loaded once and never re-fetched.

---

## Configuration

The dashboard's parameters modal (⚙ Parameters) lets you adjust the inputs
that drive the projection. See [docs/USER_GUIDE.md](docs/USER_GUIDE.md) for
the full reference, including validation rules and a description of each
chart and table column. Saved parameters persist in the local database and
are reloaded automatically on the next launch. Main parameters:

| Parameter                | Description                                         |
|---------------------------|------------------------------------------------------|
| Initial BTC stack          | Your current Bitcoin holdings, in BTC               |
| Monthly expenses            | Baseline monthly spending, in dollars              |
| Inflation rate               | Annual inflation rate (%)                         |
| Lifestyle growth           | Additional annual spending-growth rate (%)          |
| BTC spending start year      | The year your Bitcoin-funded spending begins       |
| Monthly DCA                 | Optional recurring monthly BTC purchase, in dollars |

---

## Data sources

This project relies on two external data sources, both keyless and free of
charge.

### CoinGecko

Monthly BTC/USD closing prices via CoinGecko Public API (keyless, rolling
365-day window). No API key required.

https://www.coingecko.com

### Coin Metrics

Historical seed data (2010-07 → 2026-05) sourced from Coin Metrics Community
Data, licensed under CC BY 4.0.

https://coinmetrics.io/community-network-data/

Attribution: Coin Metrics Community Data

---

## Model notes

- The "Bear" scenario is a deliberately conservative framing, not a price
  prediction.
- The price model uses a power-law exponent of 5.7675 with a time origin of
  2008.
- The projection is anchored on MM4 — a 4-year moving average of historical
  annual returns.
- The annual rate of return converges, via a sigmoid, to a 3% plateau by
  2055.

---

## License

MIT — see [LICENSE](LICENSE).
