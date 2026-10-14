"""synthetic.py: seeded synthetic Bhavcopy data generator.

Produces realistic MCX gold futures data flagged as SYNTHETIC.
Injected anomalies: stale prints, a mismatched response date, a space-padded symbol.
All randomness uses a seeded numpy.random.Generator.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np
import pandas as pd

from edge_ai.config import Config

SYNTHETIC_FLAG = True  # every row produced here carries synthetic=True


def _expiry_dates_for_month(year: int, month: int, window: tuple[int, int]) -> list[date]:
    """Return candidate expiry dates (days in window) for the given month."""
    start_day, end_day = window
    results = []
    for day in range(start_day, end_day + 1):
        try:
            results.append(date(year, month, day))
        except ValueError:
            pass
    return results


def _nearest_expiry(ref: date, window: tuple[int, int]) -> date:
    """Return the nearest upcoming expiry for a given reference date."""
    # Try current month then advance
    for delta_m in range(0, 6):
        m = ref.month + delta_m
        y = ref.year + (m - 1) // 12
        m = ((m - 1) % 12) + 1
        candidates = _expiry_dates_for_month(y, m, window)
        for c in candidates:
            if c >= ref:
                return c
    raise RuntimeError("Could not find expiry within 6 months")


def generate_bhavcopy(
    start: date,
    end: date,
    cfg: Config,
    inject_anomalies: bool = True,
) -> pd.DataFrame:
    """Generate a synthetic Bhavcopy panel for *start* to *end* (inclusive).

    Returns a DataFrame with the same columns MCX returns:
    Symbol, Date, ExpiryDate, Open, High, Low, Close, Volume, OpenInterest, synthetic.

    Anomalies injected (when inject_anomalies=True):
    - One row per ~50 rows: stale print (Close == previous Close, stale=True later)
    - One date: mismatched response date (marked in the 'date_mismatch' column)
    - One symbol: space-padded (e.g. ' GOLDM')
    """
    rng = np.random.default_rng(cfg.stats.seed)

    # Build the gold factor as a random walk (₹ per fine gram, ~7000 base)
    trading_days = pd.bdate_range(start=start, end=end)
    n = len(trading_days)
    drift = 0.0001  # ~2.5% annual on daily
    vol = 0.008
    log_ret = rng.normal(drift, vol, size=n)
    gold_px = 7000.0 * np.exp(np.cumsum(log_ret))

    # Carry ~7% annualized
    carry_ann = 0.07

    rows: list[dict] = []

    # Per-family idiosyncratic noise seed (persistent, not re-drawn each day)
    sym_noise_seeds = {sym: rng.uniform(-0.002, 0.002) for sym in cfg.data.symbols}

    for sym in cfg.data.symbols:
        c = cfg.contracts[sym]
        window = c.expiry_window
        # Small per-family drift that causes realistic cross-family parity gaps (20-120 bps)
        fam_drift = sym_noise_seeds[sym]
        # Build a random walk of family-specific noise
        fam_log_noise = np.cumsum(rng.normal(fam_drift, 0.002, size=len(trading_days)))

        for i, tday in enumerate(trading_days):
            tday_date = tday.date()
            # Find 1-2 active expiries
            front_exp = _nearest_expiry(tday_date, window)
            # Next expiry (next month)
            next_start = date(front_exp.year, front_exp.month % 12 + 1, 1) if front_exp.month < 12 else date(front_exp.year + 1, 1, 1)
            back_exp = _nearest_expiry(next_start, window)

            for exp in [front_exp, back_exp]:
                dte = (exp - tday_date).days
                if dte < 0:
                    continue
                # Price per fine gram with carry + family-specific noise
                carry_adj = math.exp(carry_ann * dte / 365)
                px_fine = gold_px[i] * carry_adj * math.exp(fam_log_noise[i])
                # Convert to quote price
                close_price = px_fine * c.fineness * c.quote_g
                # OHLC noise -- compute close first, then bound high/low
                close_p = round(close_price, 1)
                noise = rng.uniform(0.0, close_p * 0.003)
                open_p = round(close_p + rng.normal(0, noise), 1)
                high_p = round(close_p + abs(rng.normal(0, noise)), 1)
                low_p = round(close_p - abs(rng.normal(0, noise)), 1)
                # Guarantee OHLC invariants after rounding
                high_p = max(high_p, close_p, open_p)
                low_p = min(low_p, close_p, open_p)

                # Volume peaks before expiry
                vol_base = max(1.0, 200.0 - dte * 2) * rng.uniform(0.7, 1.3)
                oi_base = max(1.0, 300.0 - dte * 1.5) * rng.uniform(0.7, 1.3)
                volume = max(0, int(vol_base))
                oi = max(0, int(oi_base))

                # Stale print anomaly: ~every 50 rows, repeat close from
                # a prior row of the SAME symbol+expiry (so OHLC stays valid)
                stale_close = close_p
                stale_anomaly = False
                if inject_anomalies and rng.integers(0, 50) == 0 and len(rows) > 0:
                    prior = [r for r in rows if r["Symbol"] == sym and r["ExpiryDate"] == exp.strftime("%d%b%Y").upper()]
                    if prior:
                        stale_close = prior[-1]["Close"]
                        stale_anomaly = True
                        # Rebuild OHLC around the stale close so invariants hold
                        high_p = max(high_p, stale_close, open_p)
                        low_p = min(low_p, stale_close, open_p)

                rows.append({
                    "Symbol": sym,
                    "Date": tday_date.strftime("%m/%d/%Y"),  # MCX response format
                    "ExpiryDate": exp.strftime("%d%b%Y").upper(),
                    "Open": open_p,
                    "High": high_p,
                    "Low": low_p,
                    "Close": stale_close,
                    "Volume": volume,
                    "OpenInterest": oi,
                    "synthetic": SYNTHETIC_FLAG,
                    "_stale_injected": stale_anomaly,
                })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Inject space-padded symbol anomaly on the last GOLDM row
    if inject_anomalies and "GOLDM" in df["Symbol"].values:
        idx = df[df["Symbol"] == "GOLDM"].index[-1]
        df.at[idx, "Symbol"] = " GOLDM"

    # Inject mismatched date anomaly: one random row gets a wrong Date field
    if inject_anomalies and len(df) > 10:
        bad_idx = int(rng.integers(0, len(df) - 1))
        correct = df.at[bad_idx, "Date"]
        # Shift the date by one day
        d = pd.to_datetime(correct, format="%m/%d/%Y").date() + timedelta(days=1)
        df.at[bad_idx, "Date"] = d.strftime("%m/%d/%Y")
        df.at[bad_idx, "_date_mismatch"] = True

    if "_date_mismatch" not in df.columns:
        df["_date_mismatch"] = False

    return df


def generate_and_save(
    start: date,
    end: date,
    cfg: Config,
    raw_dir: str | None = None,
) -> pd.DataFrame:
    """Generate synthetic data and save one parquet file per date into raw_dir."""
    import pathlib

    raw_path = pathlib.Path(raw_dir or cfg.data.raw_dir)
    raw_path.mkdir(parents=True, exist_ok=True)

    df = generate_bhavcopy(start, end, cfg)
    if df.empty:
        return df

    for date_str, group in df.groupby("Date"):
        # date_str is MM/DD/YYYY — convert to YYYY-MM-DD for filename
        d = pd.to_datetime(date_str, format="%m/%d/%Y").date()
        # Skip rows with mismatched dates (they would normally be skipped by the fetcher)
        if group["_date_mismatch"].any():
            skip_path = raw_path / f"{d}.skip"
            skip_path.write_text("synthetic_date_mismatch")
            continue
        out = raw_path / f"{d}.parquet"
        group.drop(columns=["_date_mismatch", "_stale_injected"], errors="ignore").to_parquet(out, index=False)

    return df
