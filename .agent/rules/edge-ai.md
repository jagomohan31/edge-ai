 Edge AI workspace rules

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