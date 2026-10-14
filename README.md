# Edge AI

**Hack in Hills 26 | Problem Statement 03 | Commodity Derivatives Intelligence**

A cost-aware relative-value and term-structure analytics product for MCX gold futures
(GOLDM, GOLDTEN, GOLDGUINEA, GOLDPETAL), built entirely on the public MCX daily Bhavcopy.

## What it does

- Fetches and caches daily Bhavcopy, validates each date, and writes skip markers for holidays
- Cleans, deduplicates, and converts to a (symbol, expiry)-keyed panel
- Normalizes to price-per-fine-gram; computes maturity-matched parity gaps between families
- Builds term-structure curves; computes implied carry and a constant-maturity gold factor
- Raises quiet alerts only when a gap survives cost, liquidity, delivery calendar, and z-score gates
- Runs a walk-forward backtest with next-day fills, full cost model, and attribution (alpha, beta, gold P&L)
- Provides a 6-page Streamlit dashboard; shows SYNTHETIC DATA banner until real data is fetched

## Limitations

- Daily settlement prices only -- not executable fills
- Volume is not depth; liquidity gates are conservative but imperfect
- GOLDTEN history starts 1 April 2025 -- very limited back-test window
- Brokerage and cost rates are illustrative; verify before use

## Setup

```
pip install -e .[dev]
```

## Usage

```
edge-ai demo                          # end-to-end on synthetic data
edge-ai fetch --start 2025-01-02 --end 2025-06-30   # real data (needs cURL)
edge-ai build                         # panel + lifecycle
edge-ai analyze                       # curves + gaps
edge-ai signals                       # alerts
edge-ai backtest --window develop
edge-ai report
edge-ai app                           # Streamlit dashboard
```

## Human checkpoints

A: Paste the MCX cURL into `docs/bhavcopy_request.curl` before fetching real data.
B: After first fetch, confirm whether Volume is in lots or units (update `configs/default.yaml`).
C: Confirm before running the locked backtest window (runs once).
D: Replace the illustrative deck chart with the real chart from `edge-ai report`.

## Testing

```
pytest -q          # 39 tests
ruff check src tests
```
