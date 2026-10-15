# Edge AI -- MCX Gold Futures Analytics

**Hack in Hills 2026 | Problem Statement 03: Commodity Derivatives Intelligence**

A data product that transforms MCX daily Bhavcopy into relative-value analytics for gold futures (GOLDM, GOLDTEN, GOLDGUINEA, GOLDPETAL). Walk-forward backtested, cost-adjusted, with no-lookahead guarantees.

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://edge-ai-nwttdutgdhlhfbkjdhelqq.streamlit.app)

---

## Live Dashboard

```
streamlit run streamlit_app.py
```

Or via the CLI:
```
pip install -e .
edge-ai app
```

---

## What it does

| Module | Description |
|--------|-------------|
| Fetch | Parses MCX Bhavcopy cURL, fetches DD/MM/YYYY, validates MM/DD/YYYY response |
| Clean | Symbol normalisation, expiry parsing, gram conversion, stale flags |
| Normalize | Price per fine gram, log-price, parity gaps in basis points |
| Curve | Implied carry, constant-maturity gold factor G, return decomposition |
| Signals | Past-only robust z-score, all-gates alerts, no-signal records |
| Backtest | Walk-forward, t+1 fills, adverse slippage, 3-window holdout |
| Attribution | OLS gold vs relative-value decomposition, bootstrap CI, placebo |
| Dashboard | 6-page Streamlit app with live MCX fetch button |

---

## Backtest results (synthetic demo)

| Window | Trades | Net P&L | Verdict |
|--------|--------|---------|---------|
| Develop (60%) | 103 | +INR 2,26,736 | In-sample |
| Validate (20%) | 10 | +INR 16,568 | Marginal |
| **Locked (20%)** | 16 | **-INR 69,837** | **No persistent edge** |

A negative locked-window result is the honest, expected outcome -- the system correctly identifies that costs exceed any detectable gap after the baseline period.

---

## Quickstart (local)

```bash
git clone https://github.com/YOUR_USERNAME/edge-ai.git
cd edge-ai
pip install -e ".[dev]"

# Run on synthetic data (no MCX key needed)
edge-ai demo
edge-ai app
```

## Use real MCX data

1. Open https://www.mcxindia.com/market-data/bhavcopy in Chrome
2. DevTools (F12) > Network > pick a date > right-click request > Copy as cURL
3. Paste into `docs/bhavcopy_request.curl`
4. Click **Fetch Today & Rebuild** in the dashboard sidebar, OR:
   ```
   edge-ai fetch --start 2025-04-01 --end 2025-10-14
   edge-ai build
   edge-ai analyze
   edge-ai signals
   ```

---

## Deploy to Streamlit Community Cloud

1. Push this repo to GitHub (public or private)
2. Go to https://share.streamlit.io
3. Click **New app** > select this repo > set main file to `streamlit_app.py`
4. Click **Deploy**

The app runs on synthetic data by default. To use real MCX data on Cloud, add the cURL content as a Streamlit secret or pre-commit the derived parquet files.

---

## Test suite

```bash
pytest -q                     # 73 fast tests (~10s)
pytest -q -m slow             # 5 slow end-to-end self-tests (~3 min)
```

All 5 slow self-tests are acceptance criteria:
- Noise-only world produces almost no alerts
- Removing the net-edge gate loses money (CI entirely negative)
- Planted-edge world: positive P&L, beats placebo 95th percentile
- Attribution reconciles; gold < 20% of gross P&L
- Signals before a cut date do not change when later prices are added (no lookahead)

---

## Architecture

```
src/edge_ai/
    config.py       Pydantic config from configs/default.yaml
    spec.py         MCX contract constants (lot size, purity, gram weight)
    synthetic.py    Seeded synthetic Bhavcopy for tests
    fetch.py        MCX HTTP fetcher (requires cURL file)
    clean.py        Date parsing, symbol filter, gram conversion
    qa.py           7-point QA checks
    panel.py        Session-index panel builder
    normalize.py    Parity rows, log-price, gap decomposition
    curve.py        Carry, gold factor G
    lifecycle.py    Contract calendar
    liquidity.py    Past-only liquidity thresholds
    costs.py        Full cost model (CTT, exchange, stamp, SEBI, GST)
    signals.py      Walk-forward baseline, z-score, gate checks
    backtest.py     Simulator (t+1 fills, adverse slippage)
    attribution.py  P&L waterfall, OLS decomposition
    stats.py        Bootstrap CI, placebo, slippage stress
    cli.py          Typer CLI (edge-ai)
    report.py       Pipeline one-pager
    app/dashboard.py  Streamlit dashboard
```

---

## Licence

MIT