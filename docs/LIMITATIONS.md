# LIMITATIONS.md

1. Daily data only -- settlement prices are not executable intraday fills.
2. Volume is reported in lots (confirmed after first real fetch); it is not order-book depth.
3. GOLDTEN listing date is 1 April 2025 -- only ~6 months of back-test history available as of late 2025.
4. GOLDGUINEA and GOLDPETAL have thin open interest; liquidity gates filter most days out.
5. The brokerage rate (Rs 20/order) is illustrative; actual rates vary by broker and negotiation.
6. ERA5 and other reference data are not used; the product relies entirely on exchange settlement data.
7. Delivery staggering for small contracts is simplified to a fixed delivery_cutoff_sessions parameter.
8. Synthetic data (demo mode) uses a seeded random walk with injected anomalies; it does not replicate
   real MCX microstructure, seasonality, or corporate actions.
