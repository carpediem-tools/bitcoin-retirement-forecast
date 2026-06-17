# User Guide

## 1. Overview

Bitcoin Retirement Forecast is a local, single-user dashboard that projects whether
a Bitcoin stack can fund a retirement over the long term, under a deliberately
conservative ("Bear") price scenario. You enter your stack, spending, and optional
recurring purchases, and the app projects the trajectory year by year — including
the point, if any, where the stack would run out (the *runway*). It is an
educational modeling tool, not a price prediction or financial advice.

## 2. Getting started

Launch the app from the project directory:

```
python run.py
```

On first launch, the app creates a local database and loads it with a historical
seed of monthly BTC/USD closes (sourced from Coin Metrics — see *Data sources*
below). On every launch, it then syncs the most recent monthly closes from the
CoinGecko public API (no account or API key required) before opening a browser
tab with the dashboard. If the sync fails, the app continues to run on the data
already stored locally.

## 3. Header

The header shows the app title and two controls on the right:

- **Sync badge** — a small dot and label indicating whether the locally stored
  price history is current. It turns **green ("Sync OK")** when the latest
  monthly close on file is the previous calendar month, or — within the first
  few days of a new month — the month before that (a short tolerance window that
  accounts for the new month's close not being available yet). It turns
  **red ("Sync KO")** when the data looks like it may be lagging. The badge is a
  simple data-freshness indicator: it does not reflect network or connection
  status — if you need technical detail about a sync attempt, check the
  application logs.
- **⚙ Parameters button** — opens the parameters modal, where you can review and
  edit your simulation inputs (see section 8).

## 4. KPI cards

A row of summary cards sits at the top of the dashboard:

- **Theoretical ARR** — the theoretical annual rate of return the model
  projects for the upcoming year (the KPI label includes the year, e.g.
  "Theoretical ARR 2027"), under the Bear scenario's power-law decay.
- **MM anchor** — the multi-year moving average of annual returns used to anchor
  the projection's starting point (the bridge between observed history and the
  projected curve).
- **Last Monthly Close** — the most recent monthly BTC/USD closing price on file,
  with the corresponding month shown underneath. This is the reference price used
  to value your current holdings.
- **Current stack** — your current Bitcoin holdings, in BTC, as entered in
  the parameters.
- **Estimated runway** — the estimated number of years before the stack
  would be exhausted at the projected spending and growth rates (or "∞" if
  it is never exhausted within the projection horizon). The card's color
  reflects how comfortable that runway looks.

> **Note:** The "Last Monthly Close" KPI shows the most recent stored
> monthly closing price (spot). The price engine uses `anchor_price`,
> which is the rolling 12-month average of monthly closes — a distinct
> value that smooths short-term volatility. These two figures will
> generally differ, sometimes significantly.

## 5. Parameters bar

Just below the KPI cards, a compact bar recaps the simulation inputs that are
currently active: the current year, monthly spending, inflation rate,
lifestyle growth rate, the ARR plateau level and the year it is reached, and
the current portfolio value (stack valued at the last monthly close). It
gives you an at-a-glance summary of what the dashboard below is based on,
without opening the parameters modal.

> **Note:** "Projection start" displays `anchor_year + 1` — the first
> year for which a projected price is computed. For example, if the
> current anchor year is 2026, the projection starts in 2027. This is
> not the current calendar year; it is the first year beyond the last
> observed data point.

## 6. Charts

Four charts visualize the projection in detail:

- **BTC Price — Nominal & Real** — the projected Bitcoin price over time,
  shown both in nominal terms and deflated to a fixed reference year's
  purchasing power, on a logarithmic scale.
- **BTC Stack & Portfolio** — how your Bitcoin stack (in BTC) and its dollar
  value (the portfolio) evolve year by year as contributions and withdrawals
  are applied.
- **Theoretical ARR — Bear Decline** — the projected annual rate of return
  declining over time toward its long-term plateau, illustrating the Bear
  scenario's "maturing asset" assumption.
- **Cost of living — Inflation vs Lifestyle** — the projected cost of living,
  comparing a pure-inflation trajectory against one that also compounds an
  optional spending-growth ("lifestyle creep") rate.

> **Note:** The *nominal* price is the dollar figure the model
> projects for a given year — no adjustment applied. The *real* price
> re-expresses that same figure in constant purchasing power, using the
> anchor year (the "base" year shown in the chart legend, which advances
> as new data syncs in) as the reference point:
>
> `real_price(year) = nominal_price(year) / (1 + inflation_rate)^(year − anchor_year)`
>
> It answers "how much of today's purchasing power does this future price
> represent?" rather than "what will the dollar amount be?"
>
> Whether the real price keeps rising or eventually declines depends
> entirely on how the model's projected growth rate (ARR) compares to
> your configured inflation rate. As long as the projected ARR stays
> above inflation, the real price keeps climbing — more slowly than the
> nominal price, but still climbing, because Bitcoin's modeled growth
> keeps outpacing currency debasement. Once the projected ARR drops below
> inflation — which happens around 2042 under a 7% inflation assumption,
> as ARR continues converging toward its 3% long-term plateau — the real
> price starts declining even while the nominal price keeps rising. This
> is expected Bear behavior: it means Bitcoin's modeled growth no longer
> compensates for inflation in that scenario, not a flaw in the model.
> Setting an inflation rate above the long-term ARR plateau (3%) will
> always produce a declining real price in the later projection years.

## 7. Data table

Below the charts, a full year-by-year table lists every row of the projection,
historical and projected alike.

- **Filters** — three buttons let you switch the table's view between **All**,
  **Historical** (observed past data) and **Projection** (modeled future years).
- **Columns** — year, the year offset from the projection's anchor, observed and
  theoretical annual returns, nominal and real (inflation-adjusted) Bitcoin
  prices, the projected cost of living under inflation alone and under inflation
  plus lifestyle growth, the Bitcoin amount spent or contributed that year, the
  resulting stack size, and the resulting portfolio value.
- **Color coding** — figures are shown in **green** when they represent a
  positive position (e.g. a positive return, or a stack/portfolio that remains
  above zero) and in **red** when they represent a negative one (e.g. a negative
  return, or a stack/portfolio that has gone to zero or below).

## 8. Parameters modal

Opened from the ⚙ Parameters button, this form lets you adjust the inputs that
drive the projection:

- Current Bitcoin stack (in BTC)
- Monthly expenses (in dollars)
- Annual inflation rate (%)
- Annual lifestyle/spending-growth rate (%)
- The year your Bitcoin-funded spending begins
- An optional monthly recurring purchase (DCA): its amount, its annual growth
  rate, and the year it ends

The reference price used to value your stack is no longer an editable field — it
is always taken automatically from the most recent monthly close on file, so it
stays consistent with the data shown elsewhere in the dashboard.

When you save, the form validates your entries (for example, percentages and
years must fall within sensible ranges, and inconsistent combinations are
rejected with an explanation). If validation fails, an error message explains
what to correct. On a successful save, the modal closes and the entire dashboard
— KPIs, charts, parameters bar and table — recalculates and refreshes
automatically with the new inputs.

## 9. Data sources

- **Recent prices**: synced at every launch from the public **CoinGecko** API
  (keyless — no account or API key needed). All requests stay local to your
  machine; CoinGecko is the only external service the app talks to.
- **Historical seed**: the long-term monthly close history is seeded from
  **Coin Metrics Community Data**, distributed under a Creative Commons license.
  Attribution to Coin Metrics is included in the project's README.
