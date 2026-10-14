# Edge AI — Submission Checklist & Demo Guide

## Hack in Hills 26 | PS SIH-03 | Commodity Derivatives Intelligence

---

## Pre-submission checklist

### Code & tests
- [x] `pytest -q` — 39/39 tests pass
- [x] `ruff check src tests` — clean
- [x] No-lookahead property test passes: `pytest tests/test_no_lookahead.py -v`
- [x] Rebuild on held-out range works: `edge-ai rebuild --start 2026-01-05 --end 2026-04-30`
- [x] Git tagged `v0.1.0`

### Methodology
- [x] All numbers from code — zero hard-coded results
- [x] Contracts keyed by (symbol, expiry), never continuous series
- [x] Features at day t use data <= t only (proven by test_no_lookahead)
- [x] Orders fill on t+1 (proven by test_backtest)
- [x] Costs on every leg: CTT, exchange, stamp, SEBI, GST, brokerage, slippage
- [x] P&L scored on contracts actually held, at their own prices
- [x] Gold P&L separated out via OLS beta on G_ret
- [x] Locked window ran once and is guarded (runs/locked.lock)

### Results (synthetic data — replace with real after Checkpoint A+B)
| Window | Trades | Net P&L |
|---|---|---|
| Develop (60%) | 103 | INR +2,26,736 |
| Validate (20%) | 10 | INR +16,568 |
| **Locked (20%)** | **16** | **INR −69,837** |

> The locked window is negative — this is a **valid, honest result**. The spec states:
> "A rigorous demonstration that no persistent edge survives costs is a valid outcome."

### Honest caveats (shown in docs/LIMITATIONS.md)
- Daily settlement prices, not executable fills
- Volume is not depth; liquidity gates are conservative
- GOLDTEN history < 6 months
- Synthetic data used for dev — **real data requires Checkpoint A**

---

## To fetch real MCX data (Checkpoint A)

1. Go to https://www.mcxindia.com/market-data/bhavcopy
2. Open DevTools (F12) → Network tab
3. Pick any date → right-click the data request → Copy → Copy as cURL
4. Paste into `docs/bhavcopy_request.curl`
5. Run: `edge-ai fetch --start 2025-04-01 --end 2025-10-14`
6. Confirm Volume units (Checkpoint B): check sample rows, update `configs/default.yaml`
7. Run: `edge-ai build && edge-ai analyze && edge-ai signals && edge-ai backtest --window develop`
8. Checkpoint C: `edge-ai backtest --window locked` — runs once

---

## Demo script (live, synthetic data)

```
cd D:\Edge AI\edge-ai
edge-ai demo          # regenerates everything from scratch on synthetic data
edge-ai app           # opens Streamlit dashboard at http://localhost:8501
```

Pages to show:
1. **Parity Monitor** — gap history per family pair, bps scale
2. **Alerts** — 21 alerts fired; "no signal" records explain each blocked gate
3. **Backtest Lab** — equity curve, blotter, attribution waterfall
4. **Curve & Carry** — term structure, implied carry
5. **Lifecycle Calendar** — contract listing and delivery cutoff
6. **Data Health** — QA pass/fail, stale flags

Checkpoint D: replace the illustrative chart in your pitch deck with `docs/equity_chart.html`

---

## File layout

```
edge-ai/
+- src/edge_ai/          18 modules, all with docstrings
+- tests/                9 test files, 39 tests
+- configs/default.yaml  all thresholds, no magic numbers in code
+- docs/                 METHOD.md, LIMITATIONS.md, SUBMISSION.md, equity_chart.html
+- runs/                 trials.csv, 4 run directories
+- .kiro/                steering + specs (product, tech, structure, requirements, design, tasks)
+- .agent/               rules + QA workflow
```
