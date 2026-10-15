"""panel.py: build the clean panel parquet with DTE and session index."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from edge_ai.clean import clean, load_raw
from edge_ai.config import Config
from edge_ai.qa import format_qa_report, run_qa


def build_panel(cfg: Config, save: bool = True) -> pd.DataFrame:
    """Load raw data, clean it, compute DTE and session index, save panel.parquet.

    Returns the final panel DataFrame with datetime64 date/expiry columns.
    """
    raw_dir = Path(cfg.data.raw_dir)
    raw_df = load_raw(raw_dir)
    if raw_df.empty:
        raise RuntimeError(f"No raw parquet files found in {raw_dir}.")

    df, warnings = clean(raw_df, cfg)
    qa_result = run_qa(df, cfg, extra_warnings=warnings)
    print(format_qa_report(qa_result))

    # Ensure date and expiry are datetime64 (normalize.py needs .dt.days subtraction)
    df["date"]   = pd.to_datetime(df["date"])
    df["expiry"] = pd.to_datetime(df["expiry"])

    # DTE (days to expiry)
    df["dte"] = (df["expiry"] - df["date"]).dt.days

    # Session index: integer counter per trading date, sorted ascending
    dates_sorted = sorted(df["date"].unique())
    date_to_idx = {d: i for i, d in enumerate(dates_sorted)}
    df["session_idx"] = df["date"].map(date_to_idx)

    # Volume in lots (needed by backtest make_px for participation cap checks)
    df["volume"] = (df["vol_g"] / df["lot_g"]).round().astype(int)

    # Columns required by normalize.py and signals.py
    df["traded"]     = ~df["zero_vol"]
    df["ln_px_fine"] = np.log(df["px_g_fine"])

    if save:
        out_dir = Path(cfg.data.clean_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "panel.parquet"
        df.to_parquet(out_path, index=False)
        print(f"Panel saved to {out_path} ({len(df)} rows, {df['date'].nunique()} sessions)")

    return df
