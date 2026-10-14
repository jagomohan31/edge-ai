 Edge AI: the complete build script for Kiro and Google Antigravity
Everything below is also in the zip, laid out as the folders your IDE expects. Each file is shown in a fenced block under its path. Copy the blocks, or unzip the pack at the root of an empty `edge-ai/` folder.

---

## Part 0. Read me first

### `README.md`

````markdown
# Edge AI: build pack for Kiro and Google Antigravity

Hack in Hills '26 · Problem Statement 03 · Commodity Derivatives Intelligence

This pack is a spec plus ready-to-paste prompts that let an agentic IDE build the whole prototype for you: data pipeline, analytics, walk-forward backtest, dashboard. You steer and review; the agent writes the code. Both tools read the same spec files, so the work is written once.

## Setup (about 10 minutes)

1. Create an empty folder `edge-ai/` and unzip this pack at its root. You get `.kiro/`, `.agent/`, `docs/` and two prompt files.
2. Capture the MCX request (the agent must not guess it). Open the MCX Bhavcopy page, open DevTools, go to the Network tab, pick a date, right-click the data request, choose Copy, then Copy as cURL, and paste it into `docs/bhavcopy_request.curl`.
3. Check the contract constants in `.kiro/specs/edge-ai/design.md` (section "Contract constants") against the MCX gold specification page. Fix any digit that differs.

## With Kiro

1. Open the folder in Kiro. The files in `.kiro/steering/` load into every chat automatically.
2. Open chat in Spec mode and paste `KIRO_FIRST_PROMPT.md`.
3. The spec already exists in `.kiro/specs/edge-ai/`. Ask Kiro to review it rather than regenerate it. If you want to change scope, edit `product.md` and let Kiro regenerate the three spec files.
4. Run tasks one at a time from `tasks.md`. Stop at every "Human checkpoint".

## With Google Antigravity

1. Open the folder as a workspace, switch the agent to Planning mode, and set the review policy to "Request Review".
2. Paste `ANTIGRAVITY_MASTER_PROMPT.md` into the Agent Manager.
3. Check that the Implementation Plan and task list match `tasks.md`, then approve.
4. Rules live in `.agent/rules/` and workflows in `.agent/workflows/` in current builds. If yours does not pick them up, add the same text through the Customizations panel. Run the QA workflow with `/qa` after each milestone.

## Human checkpoints (the agent will stop and ask)

1. After the fetcher exists: you paste the cURL and fetch about five days of data.
2. After the first real fetch: confirm whether `Volume` is in lots or in units. The agent prints sample rows to help you decide.
3. Before the locked test window is used: confirm the choice. It can only be run once.
4. Before the pitch: replace the illustrative chart in the deck (slide "The shrinking gap") with the real chart produced by `edge-ai report`.

## Cut line if time runs short

Cut in this order: Next.js front end (not planned), placebo test, slippage-stress UI, lifecycle page, curve page. Never cut: date validation, (symbol, expiry) keys, next-day fills, costs on every leg, gold-beta attribution, quiet alerts, the locked test.

## If something goes wrong

- Fetcher returns the same day for different dates: working as designed; the validation discards those and writes skip markers.
- Normalized same-expiry prices disagree by more than 1%: almost certainly a units bug (lots vs units) or a symbol variant mixed in. Check the QA report.
- Backtest looks too good: run `pytest tests/test_no_lookahead.py` first, then look at the beta in the attribution page.
````

---

## Part A. Kiro steering

### `.kiro/steering/product.md`

````markdown
---
inclusion: always
---
# Product: Edge AI

Hack in Hills '26, Problem Statement 03: Commodity Derivatives Intelligence.

## What we are building
A cost-aware relative-value and term-structure intelligence product for MCX gold futures (GOLDM, GOLDTEN, GOLDGUINEA, GOLDPETAL), built only on the public MCX daily Bhavcopy. It explains every price gap between contracts that represent the same metal, and raises an alert only when a gap survives costs, liquidity and the delivery calendar.

## The challenge we must meet
Turn exchange settlement data into a defensible analytical signal or intelligence product, validate it on unseen history, report performance after relevant costs using the prices of the contracts actually held, and clearly separate strategy performance from the gold price itself. A rigorous demonstration that no persistent edge survives costs is a valid outcome and must be presentable.

## Principles (non-negotiable)
1. Measure before trading. No result is ever typed in or hard-coded; every number comes from code and traces to an artifact.
2. Contracts are tracked by (symbol, expiry). Never build or score on a spliced continuous series.
3. Features at day t use data up to t only. Orders created at the close of t fill on t+1.
4. Settlement prices are not executable fills and volume is not depth. Model both limits explicitly.
5. Alerts are quiet by default and always explain themselves, including the "no signal today" state.
6. Synthetic data may be used for development but must be labelled SYNTHETIC wherever it appears.
7. Publish limitations: daily data only, thin contracts, short GOLDTEN history (listed 1 April 2025).

## Users
Judges and traders. They need to see why a gap exists (purity, time, noise, residual), whether it beats costs, and what the strategy did versus gold itself.
````

### `.kiro/steering/tech.md`

````markdown
---
inclusion: always
---
# Technology

- Python 3.11+. Packages: pandas, numpy, scipy, statsmodels, pyarrow, pydantic, pyyaml, requests, typer, plotly, streamlit, pytest, ruff. DuckDB is optional.
- Package name `edge_ai` (console script `edge-ai`), src layout, installable with `pip install -e .`.
- One CLI: `python -m edge_ai <command>`. Commands are listed in the design.
- All thresholds and contract constants live in `configs/default.yaml`, validated by pydantic. No magic numbers in code.
- Dates are parsed with explicit formats only: `%m/%d/%Y` for the response Date, `%d%b%Y` for ExpiryDate, `%d/%m/%Y` for requests. Never use `dayfirst` or format inference.
- Randomness (bootstrap, placebo, synthetic data) uses a seeded `numpy.random.Generator`; the seed is in config.
- Raw data is immutable. Every derived artifact can be rebuilt from `data/raw` with one command.
- Network access happens only inside `fetch.py`. Everything else is offline and deterministic.
- Style: type hints, small pure functions, docstrings that state the formula. No notebooks in the pipeline.
- A task is done only when `pytest -q` passes and `ruff check` is clean.
````

### `.kiro/steering/structure.md`

````markdown
---
inclusion: always
---
# Project structure

```
edge-ai/
├─ .kiro/            steering + specs        .agent/   rules + workflows
├─ configs/default.yaml
├─ data/raw/         one parquet per requested date, plus .skip markers (immutable)
├─ data/clean/       panel.parquet
├─ data/derived/     factor.parquet, curves.parquet, gaps.parquet, lifecycle.parquet
├─ docs/             bhavcopy_request.curl, METHOD.md, LIMITATIONS.md
├─ runs/             trials.csv, <run_id>/ (trades, equity, attribution, summary.json)
├─ src/edge_ai/
│   ├─ cli.py config.py spec.py synthetic.py
│   ├─ fetch.py clean.py qa.py panel.py
│   ├─ normalize.py curve.py lifecycle.py
│   ├─ liquidity.py costs.py signals.py
│   ├─ backtest.py attribution.py stats.py report.py
│   └─ app/dashboard.py, app/pages/
├─ tests/            unit, property and golden tests
├─ pyproject.toml  Makefile  README.md
```

Conventions: one module per concern, no circular imports, pure functions take DataFrames and a config object, artifacts are written only by the CLI layer, the dashboard reads artifacts and never recomputes.
````

---

## Part B. Kiro spec (also read by Antigravity)

### `.kiro/specs/edge-ai/requirements.md`

````markdown
# Requirements: Edge AI

## Introduction
Edge AI converts MCX daily Bhavcopy settlement data for GOLDM, GOLDTEN, GOLDGUINEA and GOLDPETAL into an explainable, cost-aware relative-value and term-structure product, with a walk-forward backtest, honest attribution and quiet alerts. Acceptance criteria use EARS notation.

## Requirement 1: Data ingestion and validation
**User story:** As an analyst, I want every Bhavcopy day fetched once and validated, so that no mislabelled or duplicated day reaches the models.

1. WHEN a date is requested, THE Fetcher SHALL send it as DD/MM/YYYY using the request captured in `docs/bhavcopy_request.curl`.
2. WHEN the response Date (MM/DD/YYYY) differs from the requested date, THE Fetcher SHALL discard the response and write a skip marker for that date.
3. WHEN a raw file or skip marker already exists for a date, THE Fetcher SHALL NOT call the network for that date.
4. THE Fetcher SHALL wait at least `throttle_seconds` between network calls and SHALL resume an interrupted run without refetching completed dates.
5. IF `docs/bhavcopy_request.curl` is missing or cannot be parsed, THEN THE Fetcher SHALL stop with an explanatory message and SHALL NOT guess an endpoint.

## Requirement 2: Cleaning, QA and the panel
**User story:** As an analyst, I want a clean panel keyed by symbol and expiry, so that every downstream number is trustworthy.

1. THE Cleaner SHALL parse Date with `%m/%d/%Y` and ExpiryDate with `%d%b%Y`, using explicit formats only, and SHALL strip whitespace from Symbol.
2. THE Cleaner SHALL keep only configured symbols; WHEN other symbols containing GOLD exist, THE Cleaner SHALL list them in the QA report instead of silently dropping or merging them.
3. THE Cleaner SHALL key rows by (date, symbol, expiry) and SHALL reject duplicates.
4. THE Cleaner SHALL convert Volume and OpenInterest to grams using lot size, and SHALL flag rows with zero volume, or an unchanged price while neighbouring contracts moved, as stale.
5. THE QA report SHALL list rows that fail: prices greater than zero, High ≥ Close ≥ Low, days-to-expiry ≥ 0, expiry inside the configured window, and same-expiry normalized price spread of at most 1%.

## Requirement 3: Normalization and maturity matching
**User story:** As a trader, I want every contract on one comparable price scale, so that I can see which gaps are real.

1. THE Normalizer SHALL compute price per gram of fine gold as Close ÷ quote_g ÷ fineness.
2. WHEN comparing two families, THE Normalizer SHALL move one onto the other's expiry by interpolating ln(price per fine gram) along days-to-expiry within the family's own curve, extrapolating at most `max_extrapolation_days`.
3. IF fewer than two traded expiries are live in a family, or the extrapolation limit would be exceeded, THEN THE Normalizer SHALL emit no gap for that day and pair.
4. THE Normalizer SHALL express each gap in basis points as 10⁴ × ln(A at B's maturity ÷ B).
5. THE test suite SHALL include a golden test that reproduces the documented worked example (83 bps naive, 43 bps after purity, about −9 bps after carry).

## Requirement 4: Term structure and carry
**User story:** As a trader, I want mechanical roll-down separated from real curve changes, so that I do not mistake carry for signal.

1. THE Curve module SHALL compute annualized implied carry between adjacent traded expiries of each family.
2. THE Curve module SHALL compute a constant-maturity gold factor G at the configured horizon.
3. THE Curve module SHALL split each held contract's daily log return into market move, roll-down and curve change.
4. WHEN a contract has zero volume, THE Curve module SHALL exclude it from curve fitting.

## Requirement 5: Signals and gates
**User story:** As a trader, I want alerts only when a gap is meaningful, so that silence means something.

1. THE Signal module SHALL compute a robust z-score of each gap against a past-only baseline (median and MAD over `baseline_window` sessions), conditioned on a days-to-expiry bucket.
2. THE Signal module SHALL raise an alert ONLY WHEN |z| ≥ `z_threshold`, net edge ≥ `min_net_edge_bps`, liquidity gates pass for both legs on t and t−1, days-to-expiry ≥ the delivery cutoff, the price is not stale, and the maturity-matching gap ≤ `max_maturity_gap_days`.
3. WHEN an alert has fired for a pair, THE Signal module SHALL stay quiet on that pair for `cooldown_sessions` or until the gap re-crosses its baseline.
4. WHEN no alert passes, THE system SHALL write a "no signal" record naming the nearest miss and the gate that blocked it.
5. THE Signal module SHALL NOT use any data after day t when computing features for day t.

## Requirement 6: Backtest, costs and attribution
**User story:** As a judge, I want performance after costs on contracts actually held, with gold's own move removed, so that I can trust the result.

1. THE Backtester SHALL process sessions chronologically; orders created at the close of day t SHALL fill on day t+1 using the configured fill rule plus slippage.
2. THE Backtester SHALL price every leg at the actual contract's own price and lot size, and SHALL reject trades outside the contract's live window or inside the delivery cutoff.
3. THE Cost model SHALL charge CTT, exchange transaction charge, stamp duty, SEBI fee, GST and brokerage on every trade of every leg, plus slippage in ticks.
4. WHEN a leg has zero volume on the fill day, THE Backtester SHALL NOT fill it, and SHALL cap participation at `max_participation` of the day's traded grams.
5. THE Attribution module SHALL report gross spread P&L, gold-price P&L (net fine-gram exposure × change in G), costs and net strategy P&L, plus alpha and beta from a regression of daily strategy returns on gold's return.
6. THE Backtester SHALL split history by time into develop, validate and locked windows; THE locked window SHALL run once unless forced, and every configuration run SHALL be appended to `runs/trials.csv`.
7. THE Stats module SHALL report a bootstrap confidence interval of mean net P&L per trade, a placebo test, sub-period results and slippage stress at 1×, 2× and 3×.

## Requirement 7: Dashboard and alerts
**User story:** As a presenter, I want a fast dashboard that explains every number, so that I can demo live.

1. THE Dashboard SHALL provide pages: Parity monitor, Curve and carry, Lifecycle calendar, Alerts, Backtest lab, Data health.
2. THE Dashboard SHALL read only precomputed artifacts from `data/derived` and `runs`, with no heavy computation at page load.
3. WHEN the data is synthetic, THE Dashboard SHALL display a persistent SYNTHETIC DATA banner.
4. THE Alerts page SHALL show trade tickets (pair, expiry, basket, gap, baseline, z, expected convergence, cost, net edge, liquidity, exit rule) and the quiet "no signal" state.
5. EVERY number shown SHALL trace to a named artifact column.

## Requirement 8: Reproducibility and documentation
**User story:** As a judge, I want to rerun the pipeline on dates I choose, so that I can verify it.

1. `edge-ai rebuild --start YYYY-MM-DD --end YYYY-MM-DD` SHALL regenerate all derived artifacts from `data/raw`.
2. ALL thresholds SHALL come from `configs/default.yaml` and all randomness from the configured seed.
3. THE README SHALL document method, assumptions and limitations: daily data only, settlement is not an executable price, volume is not depth, GOLDTEN history is short.
4. `edge-ai report` SHALL write a one-page markdown summary containing only numbers computed by the pipeline.
5. WHEN run on a date range not seen during development, THE pipeline SHALL work without code changes.
````

### `.kiro/specs/edge-ai/design.md`

````markdown
# Design: Edge AI

## Overview
```
 MCX Bhavcopy (public)
        │  fetch.py   validate date, cache raw, throttle
        ▼
   data/raw/*.parquet ──clean.py/qa.py──▶ data/clean/panel.parquet  (key: date, symbol, expiry)
        │
        ├─ normalize.py ─▶ px per fine gram, maturity-matched parity gaps  ─▶ derived/gaps.parquet
        ├─ curve.py ─────▶ implied carry, constant-maturity gold factor    ─▶ derived/curves, factor
        └─ lifecycle.py ─▶ listing, liquidity build-up, delivery cutoff    ─▶ derived/lifecycle
                │
        signals.py + liquidity.py + costs.py ─▶ alerts / no-signal records
                │
        backtest.py ─▶ trades, equity ─▶ attribution.py + stats.py ─▶ runs/<id>/
                │
        report.py ─▶ one-page summary        app/ (Streamlit) ─▶ reads artifacts only
```

## Contract constants (verify against the MCX gold specification page)
| Symbol | lot_g | quote_g | fineness | expiry window | tick (₹ per quote unit) |
|---|---|---|---|---|---|
| GOLDM | 100 | 10 | 0.995 | 3rd–5th | 1 |
| GOLDTEN | 10 | 10 | 0.999 | 27th–31st | 1 |
| GOLDGUINEA | 8 | 8 | 0.999 | 27th–31st | 1 |
| GOLDPETAL | 1 | 1 | 0.999 | 27th–31st | 1 |

Facts the code must respect: GOLDTEN history starts 1 April 2025. Delivery on the small contracts is compulsory and staggered over the last trading days, so strategies exit before the delivery window. A contract's notional per lot is `price × lot_g / quote_g`. The smallest basket that is whole lots in all four families is 200 g (2, 20, 25 and 200 lots).

## Configuration (`configs/default.yaml`)
```yaml
data:
  raw_dir: data/raw
  throttle_seconds: 1.0
  symbols: [GOLDM, GOLDTEN, GOLDGUINEA, GOLDPETAL]
  reference_symbols: []            # add GOLD only if present and allowed by the organizers
volume_units: lots                 # confirm after the first real fetch: lots | units
contracts:
  GOLDM:      {lot_g: 100, quote_g: 10, fineness: 0.995, tick_inr: 1, expiry_window: [3, 5]}
  GOLDTEN:    {lot_g: 10,  quote_g: 10, fineness: 0.999, tick_inr: 1, expiry_window: [27, 31]}
  GOLDGUINEA: {lot_g: 8,   quote_g: 8,  fineness: 0.999, tick_inr: 1, expiry_window: [27, 31]}
  GOLDPETAL:  {lot_g: 1,   quote_g: 1,  fineness: 0.999, tick_inr: 1, expiry_window: [27, 31]}
curve:
  max_extrapolation_days: 7
  gold_factor_horizon_days: 30
signals:
  baseline_window: 60              # sessions, past only
  dte_buckets: [0, 5, 10, 20, 40, 400]
  z_threshold: 2.0
  min_net_edge_bps: 2.0
  cooldown_sessions: 5
  max_maturity_gap_days: 7
  holding_horizon_sessions: 5
  stop_z: 4.0
liquidity:
  min_traded_g_quantile: 0.25      # estimated on the develop window only
  min_oi_g_quantile: 0.25
  max_participation: 0.10
lifecycle:
  delivery_cutoff_sessions: 5      # exit at least N sessions before expiry
costs:                             # published broker rates; verify before use
  ctt_sell: 0.0001                 # 0.01% on the sell side
  exchange_txn: 0.000021           # 0.0021% both sides
  stamp_buy: 0.00002               # 0.002% on the buy side
  sebi_per_crore_inr: 10
  gst: 0.18                        # on brokerage + exchange + SEBI charges
  brokerage_per_order_inr: 20      # broker specific
  slippage_ticks_per_side: 1
  slippage_stress: [1, 2, 3]
backtest:
  fill_rule: next_open             # next_open | next_close | worst_open_close
  split: {develop: 0.6, validate: 0.2, locked: 0.2}
  basket_g: 200
  basket_multiples: 1
stats:
  bootstrap_resamples: 10000
  placebo_draws: 1000
  seed: 42
```

## Data models
- `data/raw/<YYYY-MM-DD>.parquet`: rows exactly as returned by MCX (Symbol, Date, ExpiryDate, Open, High, Low, Close, Volume, OpenInterest, any extras). `<date>.skip` marks a date that returned another day.
- `data/clean/panel.parquet`: date, symbol, expiry, open, high, low, close, volume, oi, dte, session_idx, lot_g, quote_g, fineness, px_g, px_g_fine, vol_g, oi_g, zero_vol, stale, synthetic.
- `derived/curves.parquet`: date, family, expiry, dte, ln_px_fine, traded, implied_carry_ann (to the next expiry).
- `derived/factor.parquet`: date, G (₹ per fine gram at the configured horizon), G_ret.
- `derived/gaps.parquet`: date, fam_a, fam_b, expiry_b, dte_b, gap_bps, extrap_days, liq_ok_a, liq_ok_b, stale.
- `derived/lifecycle.parquet`: symbol, expiry, first_seen, first_traded, oi_peak_date, last_traded, delivery_cutoff_date.
- `runs/<run_id>/`: trades.parquet, equity.parquet, attribution.parquet, summary.json. `runs/trials.csv` appends one row per configuration run.

## Algorithms
**Fetch.** Parse the cURL file into URL, headers and body template. Format the request date as DD/MM/YYYY. After the response, parse its Date as MM/DD/YYYY and require equality with the requested date. Write `raw/<date>.parquet` or `<date>.skip`. Sleep `throttle_seconds`. Iterate newest to oldest so recent data arrives first.

**Normalize.** `px_g = close / quote_g`; `px_g_fine = px_g / fineness`; `vol_g = volume × lot_g` (when volumes are in lots); `oi_g = oi × lot_g`.

**Maturity matching.** For one family on one date, use traded expiries only. `ln_price_at(curve, target_dte)` interpolates `ln(px_g_fine)` linearly in days-to-expiry; outside the range it extrapolates with the end slope up to `max_extrapolation_days`, otherwise returns NaN. Gap for pair (A, B) at B's expiry: `gap_bps = 1e4 × (ln_price_at(A, dte_B) − ln(px_B))`. The tradable A leg is the A contract whose expiry is closest to B's (within `max_maturity_gap_days`); the interpolated gap is the measurement, the traded contracts are scored on their own prices.

**Curve and carry.** Implied carry between neighbours: `c = 365 × ln(P2/P1) / (dte2 − dte1)`. Constant-maturity factor G: interpolate each date to `gold_factor_horizon_days`. Daily log return of a held contract ≈ `Δln G − c × Δdays/365 + remainder`, i.e. market move, mechanical roll-down, genuine curve change.

**Signals.** Per pair and days-to-expiry bucket, baseline = rolling median of past gaps, scale = 1.4826 × MAD of past gaps (past-only window). `z = (gap − baseline) / scale`. AR(1) half-life on the gap: `−ln 2 / ln φ`. Expected convergence = median change of the gap over `holding_horizon_sessions` for similar |deviation| and bucket in the develop window. `net_edge_bps = expected_convergence − round_trip_cost_bps − slippage_bps`, where round-trip cost includes the carry mismatch between the two legs' expiries.

**Costs.** Per trade leg: `notional = price × lot_g/quote_g × lots`; brokerage = `brokerage_per_order_inr` per order; CTT = `notional × ctt_sell` on sells; exchange = `notional × exchange_txn`; stamp = `notional × stamp_buy` on buys; SEBI = `notional × sebi_per_crore_inr / 1e7`; GST = `gst × (brokerage + exchange + SEBI)`; slippage = `ticks × tick_inr × lot_g/quote_g × lots`. A two-leg round trip is four trades (two buys, two sells). Sanity check for the tests: statutory costs alone come to about 3.4 bps of one leg's notional.

**Backtest loop.**
```
for t in sessions:                       # strictly chronological
    fill(pending, px[t], liquidity[t])   # decided at t-1 close, filled at t
    mark_to_market(book, px[t])          # P&L on the contracts actually held
    feats = features(panel[date <= t])   # nothing after t is visible
    pending  = exits(book, feats, calendar)    # reversion, stop_z, horizon, delivery cutoff
    pending += entries(feats, gates)           # only if every gate passes
    log(t, book, pending, feats)
```
Baskets are sized in whole lots on `basket_g` grams per leg; report residual grams and the net fine-gram exposure `E = Σ lots × lot_g × fineness`.

**Attribution.** `gold_pnl_t = E_{t−1} × (G_t − G_{t−1})`; `strategy_pnl = total − gold_pnl − costs`. Regress daily strategy return on G_ret with OLS; report alpha, beta and standard errors. Show a waterfall: gross, gold, costs, net. Benchmark: buy-and-hold of one GOLDM basket.

**Stats.** Bootstrap over trades (not days) for the mean net P&L per trade; placebo with random entry dates and the same holding-time distribution; sub-period stability by quarter; slippage stress at 1×, 2×, 3×; locked-window guard writes `runs/locked.lock` and refuses a second run unless `--force`.

**Synthetic data.** Seeded generator: gold factor as a random walk with drift, carry near 7% a year, GOLDM expiring around the 5th and the others at month-end, volume and open interest peaking before expiry, small noise and tick rounding, plus injected anomalies (stale prints, a mismatched response date, a space-padded symbol). Everything produced from it carries `synthetic = true`.

## CLI
`edge-ai fetch --start --end` · `clean` · `build` (panel, lifecycle) · `analyze` (factor, curves, gaps) · `signals` · `backtest [--locked] [--force]` · `report` · `rebuild --start --end` · `demo` (synthetic end to end) · `app`.

## Dashboard pages
1. Parity monitor: latest normalized gaps per pair, purity/time/noise/residual waterfall, cost band overlay.
2. Curve and carry: one curve per family, implied-carry history, roll-down.
3. Lifecycle calendar: listing, liquidity build-up (grams against days-to-expiry), delivery cutoff, expiry.
4. Alerts: trade tickets and the quiet state.
5. Backtest lab: net equity, attribution waterfall, trade blotter, sensitivity heatmaps, locked-test result.
6. Data health: rejected rows, stale flags, symbol variants found.

## Testing strategy
Unit tests per module; golden test for the worked example; property test `test_no_lookahead` (features at t unchanged when data after t is altered); test that fills happen at t+1; test that no trade falls outside a contract's calendar; test for the 200 g basket; tests for date parsing including `03/04/2026`; fetcher tests with mocked responses (mismatched date, holiday, cached skip).

## Risks and open questions the agent must ask the user
1. The Bhavcopy request: the user pastes the cURL; never guess the endpoint.
2. Whether `Volume` is in lots or units: print sample rows and ask.
3. Whether the 1 kg GOLD contract may be used as a reference gold factor.
4. How far back to fetch: default to as far as the page allows.
````

### `.kiro/specs/edge-ai/tasks.md`

````markdown
# Tasks: Edge AI

Priority: [MUST] [SHOULD] [COULD]. Each task ends with tests passing and `ruff check` clean. Tick the box when done.

- [ ] 0. [MUST] Scaffold the repo: `pyproject.toml`, src layout, Makefile, ruff and pytest config, pydantic config loader for `configs/default.yaml`. _Req 8_
- [ ] 1. [MUST] `spec.py`: contract constants from config, notional per lot, gram-basket helper (200 g, whole lots). Tests. _Req 3, 6_
- [ ] 2. [MUST] `synthetic.py` and `edge-ai demo`: seeded generator with injected anomalies; everything flagged `synthetic`. Tests. _Req 2, 7_
- [ ] 3. [MUST] `fetch.py`: cURL parser, DD/MM/YYYY request dates, MM/DD/YYYY response validation, raw cache, skip markers, throttling, resume. Mocked tests (mismatch, holiday, cached skip). _Req 1_
  - **Human checkpoint A:** ask the user to paste `docs/bhavcopy_request.curl` and fetch about five days.
- [ ] 4. [MUST] `clean.py` and `qa.py`: explicit parsing, symbol filter, dedupe, grams, stale flags, QA report including GOLD* symbol variants. Test `03/04/2026`. _Req 2_
  - **Human checkpoint B:** print sample rows and ask whether Volume is lots or units.
- [ ] 5. [MUST] `panel.py`: build `panel.parquet` with dte and session index. _Req 2_
- [ ] 6. [MUST] `normalize.py`: price per fine gram, `ln_price_at`, parity gaps. Golden test for the worked example (83 → 43 → about −9 bps). _Req 3_
- [ ] 7. [SHOULD] `curve.py`: implied carry, constant-maturity gold factor, return decomposition. Tests. _Req 4_
- [ ] 8. [SHOULD] `lifecycle.py`: first seen, first traded, open-interest peak, last traded, liquidity-versus-dte profile, delivery cutoff dates. _Req 6, 7_
- [ ] 9. [MUST] `liquidity.py` and `costs.py`: gates with develop-window thresholds, full cost model. Test that statutory costs come to about 3.4 bps for a two-leg round trip. _Req 5, 6_
- [ ] 10. [MUST] `signals.py`: past-only baselines, robust z, half-life, expected convergence, gates, alerts and "no signal" records. Property test `test_no_lookahead`. _Req 5_
- [ ] 11. [MUST] `backtest.py`: chronological engine, fill rules, whole-lot baskets, calendar enforcement, participation cap. Tests: t+1 fills, nothing outside the contract calendar. _Req 6_
- [ ] 12. [SHOULD] `attribution.py` and `stats.py`: P&L waterfall, beta and alpha, bootstrap, sub-periods, slippage stress, trials log, locked-run guard. _Req 6_
  - [ ] 12a. [COULD] Placebo test.
  - **Human checkpoint C:** confirm before the locked window is used; it can run once.
- [ ] 13. [MUST] `cli.py`: all commands in the design, including `rebuild --start --end`. _Req 8_
- [ ] 14. [MUST] Dashboard: Parity monitor, Alerts, Backtest lab with the SYNTHETIC DATA banner. [SHOULD] Curve and carry, Lifecycle calendar, Data health. _Req 7_
- [ ] 15. [SHOULD] `report.py`, `docs/METHOD.md`, `docs/LIMITATIONS.md`, README. Only pipeline-computed numbers. _Req 8_
- [ ] 16. [MUST] Final QA: `make qa` (pytest, ruff, rebuild from raw on a held-out range, no-lookahead test), deploy the dashboard, tag the commit. _Req 8_
  - **Human checkpoint D:** replace the illustrative chart in the pitch deck with the real one from `edge-ai report`.
````

---

## Part C. Prompts

### `KIRO_FIRST_PROMPT.md`

````markdown
Read `.kiro/steering/*.md` and `.kiro/specs/edge-ai/requirements.md`, `design.md` and `tasks.md`. The spec is already written and approved; do not regenerate it. If you see a real problem in it, tell me before changing anything.

Work through `tasks.md` one task at a time, in order:
1. Implement the task, write the tests it names, run `pytest -q` and `ruff check`.
2. Tick the checkbox in `tasks.md`.
3. Give me a three-line summary of what changed and anything surprising.
4. Stop at every "Human checkpoint" and wait for me.

Hard rules:
- Never invent the MCX endpoint. Ask me to paste the cURL into `docs/bhavcopy_request.curl`.
- Never type in or hard-code a result. If real data has not been fetched yet, use the synthetic generator and show the SYNTHETIC DATA banner.
- Respect the principles in `product.md`: (symbol, expiry) keys, past-only features, fills on t+1, costs on every leg, P&L from contracts actually held.

Start with Task 0.
````

### `ANTIGRAVITY_MASTER_PROMPT.md`

````markdown
# Mission: build Edge AI end to end

You are building a hackathon prototype: a cost-aware relative-value and term-structure intelligence product for MCX gold futures (GOLDM, GOLDTEN, GOLDGUINEA, GOLDPETAL), using only the public MCX daily Bhavcopy. The spec is in the workspace:

- `.kiro/steering/product.md`, `tech.md`, `structure.md` (principles, stack, layout)
- `.kiro/specs/edge-ai/requirements.md`, `design.md`, `tasks.md` (what to build, how, in what order)
- `.agent/rules/edge-ai.md` (guardrails)

## How to work
1. Planning mode. First produce an Implementation Plan and a task list that mirror `tasks.md`. Wait for my approval.
2. Then execute task by task. After each task: run `pytest -q` and `ruff check`, tick the box in `tasks.md`, and summarise in three lines.
3. Stop and ask me at each "Human checkpoint" in `tasks.md`.
4. Use the QA workflow (`/qa`) after every milestone (tasks 6, 11, 14, 16).

## Hard rules
- Do not guess the MCX endpoint. Ask me to paste the cURL into `docs/bhavcopy_request.curl`.
- Do not fabricate or hard-code results. Every number must come from code and trace to an artifact. Until real data is fetched, use the synthetic generator and show a SYNTHETIC DATA banner.
- Key everything by (symbol, expiry). Never build or score a continuous series.
- Features at day t use data up to t only; orders fill on t+1.
- Charge costs on every leg; score P&L on the contracts actually held; separate gold's own move in the attribution.
- Alerts are quiet by default and explain themselves, including the "no signal" state.

## Deliverables
A package `edge_ai` with the CLI in the design, passing tests, a Streamlit dashboard with the six pages, `docs/METHOD.md` and `docs/LIMITATIONS.md`, a README, and a `edge-ai report` one-pager of pipeline-computed numbers.

## Verification
Show me: the no-lookahead test passing, the worked-example golden test (83 → 43 → about −9 bps), a rebuild from raw on a held-out date range, and the dashboard running on both synthetic and real data.
````

---

## Part D. Antigravity rules and workflow

### `.agent/rules/edge-ai.md`

````markdown
# Edge AI workspace rules

- Never fabricate or hard-code results. Every number comes from code and traces to an artifact column.
- Parse dates with explicit formats only: response Date `%m/%d/%Y`, ExpiryDate `%d%b%Y`, request `%d/%m/%Y`. Never infer or use dayfirst.
- Compare the response Date with the requested date; discard mismatches and write a skip marker.
- Key all data by (symbol, expiry). Never splice a continuous series, and never score on one.
- Features at day t use data up to t only. Orders created at the close of t fill on t+1.
- Settlement prices are not executable fills; volume is not depth. Use liquidity gates and slippage.
- Charge CTT, exchange, stamp, SEBI, GST, brokerage and slippage on every leg. Score P&L on contracts actually held.
- All thresholds live in `configs/default.yaml`. Seeds are fixed. Raw data is immutable.
- Synthetic data must be flagged `synthetic` and the UI must show a SYNTHETIC DATA banner.
- Do not guess the MCX endpoint; ask the user for `docs/bhavcopy_request.curl`.
- A task is done only when `pytest -q` passes and `ruff check` is clean.
````

### `.agent/workflows/qa.md`

````markdown
# QA

Run the full quality check for Edge AI and report results:
1. `ruff check` and `pytest -q`. List any failure with the file and line.
2. Run `pytest tests/test_no_lookahead.py -q` on its own and confirm it passes.
3. Run `python -m edge_ai rebuild` on a held-out date range that was not used during development and confirm every artifact regenerates without code changes.
4. Open the dashboard on synthetic data and on real data (if fetched) and confirm every page loads and the SYNTHETIC DATA banner appears only for synthetic data.
5. Check that no number in `docs/` or the README is hard-coded; each must come from `edge-ai report`.
6. Summarise: what passed, what failed, what to fix next.
````

---

## Part E. Placeholder you fill in

### `docs/bhavcopy_request.curl`

````markdown
# Paste ONE cURL command here (DevTools > Network > right-click the data request > Copy > Copy as cURL).
# The fetcher parses the URL, headers and body from this file and substitutes the date (DD/MM/YYYY).
# Do not commit cookies or tokens if the repo is public.
````
