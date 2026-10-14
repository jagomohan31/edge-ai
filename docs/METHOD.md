# METHOD.md

## Data source
MCX daily Bhavcopy, fetched via a captured HTTP request (see `docs/bhavcopy_request.curl`).
Symbols: GOLDM, GOLDTEN, GOLDGUINEA, GOLDPETAL. Dates validated: response Date must equal requested date.

## Normalization
Price per fine gram: `px_g_fine = close / quote_g / fineness`.
Parity gaps: `gap_bps = 1e4 * (ln_price_at(A, dte_B) - ln(px_g_fine_B))`.
Maturity matching by linear interpolation of ln(price) along DTE; extrapolation capped at 7 days.

## Signals
Robust z-score: `z = (gap - median_past) / (1.4826 * MAD_past)` over a 60-session past-only window,
conditioned on DTE bucket. Alert fires only when |z| >= 2.0, net_edge >= 2 bps, both liquidity
gates pass, DTE >= delivery cutoff, price is not stale, and the pair is out of cooldown.

## Backtest
Chronological engine. Orders at close of day t fill at open of day t+1. P&L scored on the actual
held contracts at their own prices. Costs: CTT, exchange transaction charge, stamp, SEBI, GST,
brokerage, slippage (1 tick/side). Attribution: gold P&L regressed out via OLS beta on G_ret.
