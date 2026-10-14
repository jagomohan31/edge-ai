"""liquidity.py: liquidity gates calibrated on the develop window (Req 5, 6)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from edge_ai.config import Config


def calibrate_liquidity(panel: pd.DataFrame, cfg: Config, develop_mask: pd.Series) -> dict:
    """Compute liquidity thresholds from the develop window.

    Returns a dict with per-symbol thresholds: {symbol: {vol_g_min, oi_g_min}}.
    """
    dev = panel[develop_mask]
    thresholds: dict[str, dict] = {}
    for sym in cfg.data.symbols:
        sym_dev = dev[dev["symbol"] == sym]
        vol_min = float(np.nanquantile(sym_dev["vol_g"], cfg.liquidity.min_traded_g_quantile)) if not sym_dev.empty else 0.0
        oi_min = float(np.nanquantile(sym_dev["oi_g"], cfg.liquidity.min_oi_g_quantile)) if not sym_dev.empty else 0.0
        thresholds[sym] = {"vol_g_min": vol_min, "oi_g_min": oi_min}
    return thresholds


def liquidity_ok(row: pd.Series, thresholds: dict, cfg: Config) -> bool:
    """Return True if the row passes the liquidity gate."""
    sym = row["symbol"]
    if sym not in thresholds:
        return False
    t = thresholds[sym]
    return (
        float(row["vol_g"]) >= t["vol_g_min"]
        and float(row["oi_g"]) >= t["oi_g_min"]
    )
