"""clean.py: clean raw Bhavcopy parquet files into a validated panel.

Rules (Req 2):
- Parse Date with %m/%d/%Y, ExpiryDate with %d%b%Y (explicit formats only).
- Strip whitespace from Symbol.
- Keep only configured symbols; list GOLD* variants in QA report.
- Key by (date, symbol, expiry); reject duplicates.
- Convert Volume and OpenInterest to grams using lot size.
- Flag zero-volume rows and stale rows (unchanged Close while neighbours moved).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from edge_ai.config import Config

_DATE_FMT = "%m/%d/%Y"
_EXPIRY_FMT = "%d%b%Y"


class ParseError(ValueError):
    """Raised when a raw file cannot be parsed."""


def load_raw(raw_dir: Path) -> pd.DataFrame:
    """Load all parquet files from raw_dir into a single DataFrame."""
    files = sorted(raw_dir.glob("*.parquet"))
    if not files:
        return pd.DataFrame()
    frames = [pd.read_parquet(f) for f in files]
    return pd.concat(frames, ignore_index=True)


def clean(raw_df: pd.DataFrame, cfg: Config) -> tuple[pd.DataFrame, list[str]]:
    """Clean a raw DataFrame.

    Returns (clean_df, qa_warnings).
    """
    warnings: list[str] = []
    df = raw_df.copy()

    if df.empty:
        return df, warnings

    # Strip whitespace from Symbol
    df["Symbol"] = df["Symbol"].astype(str).str.strip()

    # Parse Date (MM/DD/YYYY)
    try:
        df["date"] = pd.to_datetime(df["Date"], format=_DATE_FMT).dt.date
    except Exception as exc:
        raise ParseError(f"Date column parse failure: {exc}") from exc

    # Parse ExpiryDate (ddMonYYYY, e.g. 05OCT2025)
    try:
        df["expiry"] = pd.to_datetime(df["ExpiryDate"].str.strip(), format=_EXPIRY_FMT).dt.date
    except Exception as exc:
        raise ParseError(f"ExpiryDate column parse failure: {exc}") from exc

    # Identify GOLD* symbol variants not in the config
    gold_variants = df[df["Symbol"].str.upper().str.startswith("GOLD")]["Symbol"].unique()
    extra = [s for s in gold_variants if s not in cfg.data.symbols]
    for s in extra:
        warnings.append(f"GOLD* variant found but not in config (will be dropped): {s!r}")

    # Keep only configured symbols
    df = df[df["Symbol"].isin(cfg.data.symbols)].copy()
    if df.empty:
        warnings.append("No rows remain after symbol filter.")
        return df, warnings

    # Rename columns
    df = df.rename(columns={
        "Symbol": "symbol",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume_raw",
        "OpenInterest": "oi_raw",
    })

    # Deduplicate on (date, symbol, expiry)
    key = ["date", "symbol", "expiry"]
    dupes = df.duplicated(subset=key, keep=False)
    if dupes.any():
        n = dupes.sum()
        warnings.append(f"{n} duplicate (date, symbol, expiry) rows found; keeping first.")
        df = df.drop_duplicates(subset=key, keep="first")

    # Attach contract metadata
    df["lot_g"] = df["symbol"].map(lambda s: cfg.contracts[s].lot_g)
    df["quote_g"] = df["symbol"].map(lambda s: cfg.contracts[s].quote_g)
    df["fineness"] = df["symbol"].map(lambda s: cfg.contracts[s].fineness)

    # Compute price per gram and per fine gram
    df["px_g"] = df["close"] / df["quote_g"]
    df["px_g_fine"] = df["px_g"] / df["fineness"]

    # Convert volume to grams
    if cfg.volume_units == "lots":
        df["vol_g"] = df["volume_raw"] * df["lot_g"]
        df["oi_g"] = df["oi_raw"] * df["lot_g"]
    else:
        df["vol_g"] = df["volume_raw"]
        df["oi_g"] = df["oi_raw"]

    # Zero-volume flag
    df["zero_vol"] = df["vol_g"] == 0

    # Stale flag: Close unchanged while same-date neighbours moved
    df = df.sort_values(["date", "symbol", "expiry"]).reset_index(drop=True)
    df["stale"] = False
    for (_date_val, _sym), grp in df.groupby(["date", "symbol"]):
        if len(grp) < 2:
            continue
        median_move = grp["close"].diff().abs().median()
        if median_move > 0:
            # Rows where this contract's close did not move relative to prior session
            stale_mask = grp["close"].diff().abs() == 0
            df.loc[stale_mask[stale_mask].index, "stale"] = True

    # synthetic flag passthrough
    if "synthetic" not in df.columns:
        df["synthetic"] = False

    final_cols = [
        "date", "symbol", "expiry",
        "open", "high", "low", "close",
        "vol_g", "oi_g", "zero_vol", "stale",
        "lot_g", "quote_g", "fineness",
        "px_g", "px_g_fine", "synthetic",
    ]
    available = [c for c in final_cols if c in df.columns]
    return df[available].reset_index(drop=True), warnings
