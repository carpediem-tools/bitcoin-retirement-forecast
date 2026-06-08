# bitcoin-retirement-bear

> Local web app modeling the viability of a Bitcoin-funded retirement under a conservative **Bear** scenario.
> **Not financial advice. Not a price-prediction tool.**

A clone-and-run desktop web application that projects whether a Bitcoin stack can sustain a retirement, year by year, out to **2072** — under a deliberately conservative appreciation model. It runs entirely on your machine: your inputs never leave your computer.

---

## ⚠️ Disclaimer

This is an **educational modeling tool**, not investment advice and not a forecast of Bitcoin's price. It projects *one* explicit, conservative scenario from assumptions you control. Real markets will diverge — likely a lot. Do not make financial decisions based on this output. Consult a qualified professional.

## What it does

Given your starting stack, contributions, and spending, the app projects a single conservative trajectory and answers one question: **how long does the stack last?**

- **Bear scenario, not a bull pitch.** Most Bitcoin retirement calculators assume optimistic growth. This one applies a power-law appreciation model, discounted for a bearish view, converging toward a low long-term plateau.
- **Runway as the headline number.** The model reports the first year the stack goes negative (the *runway*), and keeps projecting past it so you can see the full picture.
- **Two independent cash-flow streams.** Optional **DCA** accumulation and **drawdown** spending can run in parallel, not just sequentially.
- **Real purchasing power.** Living costs compound with inflation and an optional spending-growth rate; nominal results can be deflated to today's value.
- **Local and private.** Monthly BTC/USD closes are stored in a local SQLite database (history since 2010). On launch the app syncs recent closes from the public CoinGecko API — **no API key required, ever**.

## How the model works (high level)

1. **Aggregation** — derives the anchor (last real year/price) and a moving-average ARR from stored monthly closes.
2. **Price engine** — projects a nominal yearly BTC price: power law → blend toward the anchor MM → bear discount → sigmoid convergence toward a fixed 3% plateau at 2055.
3. **Flow engine** — applies DCA, drawdown, and inflation-compounded living costs to track the stack, portfolio value, and runway.

The price model uses fixed calendar rails (power-law time origin, sigmoid convergence) so that maturity is tied to real calendar time, not to when you happen to run the app. Integrity constants are not user-tunable; user inputs cover stack, contributions, spending, and rates only.

## Stack

- **Python 3.13** · **Flask** (routes) + **waitress** (WSGI server)
- **SQLite** (persisted monthly closes)
- **Pydantic** (input validation) · **requests** (CoinGecko, keyless)
- Frontend: single-page dashboard (Chart.js)

## Quick start

```bash
git clone https://github.com/<your-handle>/btc-retirement-bear.git
cd btc-retirement-bear
pip install -r requirements.txt
python run.py
```

`run.py` starts waitress on `http://127.0.0.1:8000` (falls back to 8001, 8002… if busy) and opens your browser once the server is listening. Single-user, localhost-only, no authentication.

## Data & privacy

All data — your inputs and the monthly-close database — stays on your machine. The only network call is a single keyless request to CoinGecko at launch to refresh recent closes. If that call fails, the app runs in a degraded sync state on existing local data.

Historical data: Coin Metrics Community Data (CC license) github.com/coinmetrics/data

## License

[MIT](LICENSE)

---

*Suggested GitHub topics:* `bitcoin` · `retirement-calculator` · `retirement-planning` · `financial-modeling` · `power-law` · `python` · `flask` · `local-first`
