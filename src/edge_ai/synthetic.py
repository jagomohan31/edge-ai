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


# ---------------------------------------------------------------------------
# Reference-compatible make_synthetic_panel (used by slow self-tests)
# ---------------------------------------------------------------------------

def _month_end(ts) -> pd.Timestamp:
    """Last business day of the month containing ts."""
    return pd.Timestamp(ts) + pd.offsets.BMonthEnd(0)


def _fifth(y: int, m: int) -> pd.Timestamp:
    """The 5th of month m/y, or the previous business day if it falls on a weekend."""
    d = pd.Timestamp(y, m, 5)
    return d if d.weekday() < 5 else d - pd.offsets.BDay(1)


def make_synthetic_panel(
    start: str = "2025-01-01",
    end: str = "2026-09-30",
    cfg: Config | None = None,
    seed: int = 7,
    mode: str = "noise_only",
    carry: float = 0.07,
) -> pd.DataFrame:
    """Reference-compatible synthetic panel generator.

    mode='noise_only'    : settlement noise that is NOT tradable at the next open.
    mode='planted_edge'  : adds persistent AR(1) mispricing in the small contracts.

    Returns a clean panel DataFrame with columns:
    date, symbol, expiry, open, high, low, close, volume, oi, synthetic.
    """
    from edge_ai.config import load_config as _load
    if cfg is None:
        cfg = _load()

    FAMS = ["GOLDM", "GOLDTEN", "GOLDGUINEA", "GOLDPETAL"]
    rng = np.random.default_rng(seed)
    sessions = pd.bdate_range(start, end)
    n = len(sessions)

    logS = np.log(8000.0) + np.cumsum(rng.normal(0.0004, 0.008, n))
    S_close = np.exp(logS)
    S_open  = np.exp(np.r_[logS[0], logS[:-1]] + 0.5 * np.diff(np.r_[logS[0], logS]))

    months = pd.period_range(
        pd.Timestamp(start) - pd.offsets.MonthBegin(2),
        pd.Timestamp(end)   + pd.offsets.MonthBegin(5),
        freq="M",
    )
    exp_map = {"GOLDM": [_fifth(p.year, p.month) for p in months]}
    for f in FAMS[1:]:
        exp_map[f] = [_month_end(p.start_time) for p in months]

    delta: dict[str, np.ndarray] = {f: np.zeros(n) for f in FAMS}
    if mode == "planted_edge":
        for f, sig in (("GOLDTEN", 8.0), ("GOLDGUINEA", 10.0), ("GOLDPETAL", 12.0)):
            x = 0.0
            for i in range(n):
                x = 0.8 * x + rng.normal(0, sig * np.sqrt(1 - 0.8 ** 2))
                delta[f][i] = x * 1e-4

    settle_sd = {"GOLDM": 0.3, "GOLDTEN": 1.5, "GOLDGUINEA": 2.0, "GOLDPETAL": 2.5}
    open_sd   = {"GOLDM": 0.3, "GOLDTEN": 0.8, "GOLDGUINEA": 0.8, "GOLDPETAL": 0.8}
    base_vol  = {"GOLDM": 14000, "GOLDTEN": 600, "GOLDGUINEA": 1200, "GOLDPETAL": 8000}

    rows = []
    for i, d in enumerate(sessions):
        for f in FAMS:
            live = sorted(e for e in exp_map[f] if 0 <= (e - d).days <= 100)
            for r, e in enumerate(live):
                dte        = (e - d).days
                c          = cfg.contracts[f]
                carry_f    = np.exp(carry * dte / 365)
                cl_fine    = S_close[i] * carry_f * np.exp(
                    delta[f][i] + rng.normal(0, settle_sd[f]) * 1e-4
                )
                prev_d     = 0.8 * delta[f][i - 1] if i > 0 else 0.0
                op_fine    = S_open[i]  * carry_f * np.exp(
                    prev_d + rng.normal(0, open_sd[f]) * 1e-4
                )
                # price = fine_price * fineness * quote_g, rounded to tick
                def _q(fine_px: float, _c=c) -> float:
                    return float(np.round(fine_px * _c.fineness * _c.quote_g))

                close_p = _q(cl_fine)
                open_p  = _q(op_fine)
                vol = 0 if r >= 3 else int(
                    base_vol[f] * 0.45 ** r
                    * (0.4 + 1.2 * np.exp(-dte / 15))
                    * rng.lognormal(0, 0.4)
                )
                high_p = max(open_p, close_p) + 1
                low_p  = min(open_p, close_p) - 1
                rows.append((d, f, e, open_p, high_p, low_p, close_p, vol, vol * 6))

    df = pd.DataFrame(
        rows,
        columns=["date", "symbol", "expiry", "open", "high", "low", "close", "volume", "oi"],
    )
    df["date"]   = pd.to_datetime(df["date"])
    df["expiry"] = pd.to_datetime(df["expiry"])
    df["synthetic"] = True
    return df
