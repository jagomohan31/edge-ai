"""curve.py: term structure and carry module (Requirement 4).

- Annualized implied carry between adjacent traded expiries.
- Constant-maturity gold factor G at the configured horizon.
- Daily log return decomposition: market move + roll-down + curve change.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from edge_ai.config import Config


def compute_curves(panel: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Compute per-date, per-family curve with implied carry.

    Returns DataFrame: date, family, expiry, dte, ln_px_fine, traded, implied_carry_ann.
    Excludes zero-volume rows from curve fitting (Req 4.4).
    """
    if "ln_px_fine" not in panel.columns:
        panel = panel.copy()
        panel["ln_px_fine"] = np.log(panel["px_g_fine"])

    records: list[dict] = []

    for (date_val, sym), grp in panel.groupby(["date", "symbol"]):
        traded = grp[~grp["zero_vol"]].sort_values("dte")

        for _, row in grp.sort_values("dte").iterrows():
            rec: dict = {
                "date": date_val,
                "family": sym,
                "expiry": row["expiry"],
                "dte": row["dte"],
                "ln_px_fine": row["ln_px_fine"] if not row["zero_vol"] else float("nan"),
                "traded": not row["zero_vol"],
                "implied_carry_ann": float("nan"),
            }
            records.append(rec)

        # Implied carry between adjacent traded expiries
        # c = 365 * ln(P2/P1) / (dte2 - dte1)
        if len(traded) >= 2:
            for i in range(len(traded) - 1):
                r1 = traded.iloc[i]
                r2 = traded.iloc[i + 1]
                dte1, dte2 = float(r1["dte"]), float(r2["dte"])
                ln1, ln2 = float(r1["ln_px_fine"]), float(r2["ln_px_fine"])
                if dte2 != dte1:
                    carry = 365.0 * (ln2 - ln1) / (dte2 - dte1)
                    # Attach to the nearer-expiry row
                    for rec in records:
                        if rec["date"] == date_val and rec["family"] == sym and rec["expiry"] == r1["expiry"]:
                            rec["implied_carry_ann"] = carry
                            break

    return pd.DataFrame(records)


def compute_gold_factor(curves_df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Compute constant-maturity gold factor G (₹ per fine gram at configured horizon).

    Interpolates each date's GOLDM (or first available family) to gold_factor_horizon_days.
    Returns DataFrame: date, G, G_ret.
    """
    horizon = cfg.curve.gold_factor_horizon_days
    max_extrap = cfg.curve.max_extrapolation_days

    records: list[dict] = []
    families = cfg.data.symbols

    for date_val, grp in curves_df.groupby("date"):
        G_val = float("nan")
        for fam in families:
            fam_df = grp[(grp["family"] == fam) & grp["traded"]].dropna(subset=["ln_px_fine"])
            if len(fam_df) < 2:
                continue
            sdf = fam_df.sort_values("dte")
            x = sdf["dte"].to_numpy(float)
            y = sdf["ln_px_fine"].to_numpy(float)
            h = float(horizon)
            if x[0] <= h <= x[-1]:
                ln_g = float(np.interp(h, x, y))
            else:
                k, j = (0, 1) if h < x[0] else (-1, -2)
                if abs(h - x[k]) > max_extrap:
                    continue
                ln_g = float(y[k] + (y[k]-y[j])/(x[k]-x[j]) * (h - x[k]))
            G_val = float(np.exp(ln_g))
            break
        records.append({"date": date_val, "G": G_val})

    factor_df = pd.DataFrame(records).sort_values("date").reset_index(drop=True)
    factor_df["G_ret"] = np.log(factor_df["G"]).diff()
    return factor_df


def decompose_returns(
    panel: pd.DataFrame,
    curves_df: pd.DataFrame,
    factor_df: pd.DataFrame,
) -> pd.DataFrame:
    """Decompose daily log return of a held contract into:

    market_move = Δln G
    roll_down   = -implied_carry_ann * Δdays / 365
    curve_change = remainder = total_log_ret - market_move - roll_down

    Returns panel with additional columns: log_ret, market_move, roll_down, curve_change.
    """
    panel = panel.copy().sort_values(["symbol", "expiry", "date"])
    panel["log_ret"] = panel.groupby(["symbol", "expiry"])["ln_px_fine"].diff()

    # Merge gold factor return
    panel = panel.merge(factor_df[["date", "G_ret"]], on="date", how="left")
    panel = panel.rename(columns={"G_ret": "market_move"})

    # Merge implied carry
    carry_map = curves_df[["date", "family", "expiry", "implied_carry_ann"]].rename(
        columns={"family": "symbol"}
    )
    panel = panel.merge(carry_map, on=["date", "symbol", "expiry"], how="left")

    # Roll-down: -carry * delta_days/365 (delta_days = -1 for each trading day)
    panel["roll_down"] = panel["implied_carry_ann"] * (-1.0) / 365.0

    # Curve change = residual
    panel["curve_change"] = panel["log_ret"] - panel["market_move"].fillna(0) - panel["roll_down"].fillna(0)

    return panel
