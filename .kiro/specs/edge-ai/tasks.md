 Tasks: Edge AI

Priority: [MUST] [SHOULD] [COULD]. Each task ends with tests passing and `ruff check` clean. Tick the box when done.

- [x] 0. [MUST] Scaffold the repo: `pyproject.toml`, src layout, Makefile, ruff and pytest config, pydantic config loader for `configs/default.yaml`. _Req 8_
- [x] 1. [MUST] `spec.py`: contract constants from config, notional per lot, gram-basket helper (200 g, whole lots). Tests. _Req 3, 6_
- [x] 2. [MUST] `synthetic.py` and `edge-ai demo`: seeded generator with injected anomalies; everything flagged `synthetic`. Tests. _Req 2, 7_
- [x] 3. [MUST] `fetch.py`: cURL parser, DD/MM/YYYY request dates, MM/DD/YYYY response validation, raw cache, skip markers, throttling, resume. Mocked tests (mismatch, holiday, cached skip). _Req 1_
  - **Human checkpoint A:** ask the user to paste `docs/bhavcopy_request.curl` and fetch about five days.
- [x] 4. [MUST] `clean.py` and `qa.py`: explicit parsing, symbol filter, dedupe, grams, stale flags, QA report including GOLD* symbol variants. Test `03/04/2026`. _Req 2_
  - **Human checkpoint B:** print sample rows and ask whether Volume is lots or units.
- [x] 5. [MUST] `panel.py`: build `panel.parquet` with dte and session index. _Req 2_
- [x] 6. [MUST] `normalize.py`: price per fine gram, `ln_price_at`, parity gaps. Golden test for the worked example (83 -> 43 -> about -9 bps). _Req 3_
- [x] 7. [SHOULD] `curve.py`: implied carry, constant-maturity gold factor, return decomposition. Tests. _Req 4_
- [x] 8. [SHOULD] `lifecycle.py`: first seen, first traded, open-interest peak, last traded, liquidity-versus-dte profile, delivery cutoff dates. _Req 6, 7_
- [x] 9. [MUST] `liquidity.py` and `costs.py`: gates with develop-window thresholds, full cost model. Test that statutory costs come to about 3.4 bps for a two-leg round trip. _Req 5, 6_
- [x] 10. [MUST] `signals.py`: past-only baselines, robust z, half-life, expected convergence, gates, alerts and "no signal" records. Property test `test_no_lookahead`. _Req 5_
- [x] 11. [MUST] `backtest.py`: chronological engine, fill rules, whole-lot baskets, calendar enforcement, participation cap. Tests: t+1 fills, nothing outside the contract calendar. _Req 6_
- [x] 12. [SHOULD] `attribution.py` and `stats.py`: P&L waterfall, beta and alpha, bootstrap, sub-periods, slippage stress, trials log, locked-run guard. _Req 6_
  - [x] 12a. [COULD] Placebo test.
  - **Human checkpoint C:** confirm before the locked window is used; it can run once.
- [x] 13. [MUST] `cli.py`: all commands in the design, including `rebuild --start --end`. _Req 8_
- [x] 14. [MUST] Dashboard: Parity monitor, Alerts, Backtest lab with the SYNTHETIC DATA banner. [SHOULD] Curve and carry, Lifecycle calendar, Data health. _Req 7_
- [x] 15. [SHOULD] `report.py`, `docs/METHOD.md`, `docs/LIMITATIONS.md`, README. Only pipeline-computed numbers. _Req 8_
- [x] 16. [MUST] Final QA: `make qa` (pytest, ruff, rebuild from raw on a held-out range, no-lookahead test), deploy the dashboard, tag the commit. _Req 8_
  - **Human checkpoint D:** replace the illustrative chart in the pitch deck with the real one from `edge-ai report`.