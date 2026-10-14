--
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