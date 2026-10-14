"""normalize.py: price per fine gram, maturity-matched parity gaps.

Requirement 3:
- px_g_fine = close / quote_g / fineness
- ln_price_at: interpolate ln(px_g_fine) along DTE; extrapolate up to max_extrapolation_days
- gap_bps = 1e4 * (ln_price_at(A, dte_B) - ln(px_B))

Golden test: 83 bps naive -> 43 bps after purity -> ~-9 bps after carry.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from edge_ai.config import Config


def ln_price_at(
    curve_df: pd.DataFrame,
    target_dte: float,
    max_extrapolation_days: int,
) -> float | None:
    """Interpolate ln(px_g_fine) at target_dte from a family's traded curve.

    curve_df must have columns: dte, ln_px_fine (sorted by dte ascending).
    Returns None if target_dte is out of range by more than max_extrapolation_days.
    """
    df = curve_df.dropna(subset=["dte", "ln_px_fine"]).sort_values("dte")
    if len(df) < 2:
        return None

    dte_arr = df["dte"].values.astype(float)
    ln_arr = df["ln_px_fine"].values.astype(float)

    min_dte, max_dte = dte_arr[0], dte_arr[-1]

    if min_dte <= target_dte <= max_dte:
        return float(np.interp(target_dte, dte_arr, ln_arr))

    # Extrapolation
    if target_dte < min_dte:
        if min_dte - target_dte > max_extrapolation_days:
            return None
        # End slope at min
        slope = (ln_arr[1] - ln_arr[0]) / (dte_arr[1] - dte_arr[0]) if len(dte_arr) > 1 else 0.0
        return float(ln_arr[0] + slope * (target_dte - dte_arr[0]))
    else:
        if target_dte - max_dte > max_extrapolation_days:
            return None
        slope = (ln_arr[-1] - ln_arr[-2]) / (dte_arr[-1] - dte_arr[-2]) if len(dte_arr) > 1 else 0.0
        return float(ln_arr[-1] + slope * (target_dte - dte_arr[-1]))


def compute_gaps(panel: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Compute maturity-matched parity gaps across all symbol pairs.

    For each trading date and pair (fam_a, fam_b):
    gap_bps = 1e4 * (ln_price_at(A, dte_B) - ln(px_g_fine_B))

    Returns a DataFrame with columns:
    date, fam_a, fam_b, expiry_b, dte_b, gap_bps, extrap_days, liq_ok_a, liq_ok_b, stale
    """
    symbols = cfg.data.symbols
    max_extrap = cfg.curve.max_extrapolation_days
    max_maturity_gap = cfg.signals.max_maturity_gap_days

    if "ln_px_fine" not in panel.columns:
        panel = panel.copy()
        panel["ln_px_fine"] = np.log(panel["px_g_fine"])

    records: list[dict] = []

    for date_val, day_df in panel.groupby("date"):
        # Build per-family curves (traded expiries only, non-zero vol)
        family_curves: dict[str, pd.DataFrame] = {}
        for sym in symbols:
            sym_df = day_df[
                (day_df["symbol"] == sym) & (~day_df["zero_vol"])
            ][["dte", "ln_px_fine", "expiry"]].dropna().sort_values("dte")
            if len(sym_df) >= 2:
                family_curves[sym] = sym_df

        # Pairwise gaps
        for i, fam_a in enumerate(symbols):
            for fam_b in symbols[i + 1:]:
                if fam_a not in family_curves or fam_b not in family_curves:
                    continue

                curve_a = family_curves[fam_a]

                # For each expiry in B, compute gap
                for _, row_b in day_df[day_df["symbol"] == fam_b].iterrows():
                    dte_b = row_b["dte"]
                    ln_b = row_b["ln_px_fine"]
                    if pd.isna(ln_b) or pd.isna(dte_b):
                        continue

                    # Check maturity gap: closest A expiry to B expiry
                    dte_a_arr = curve_a["dte"].values
                    nearest_idx = int(np.argmin(np.abs(dte_a_arr - dte_b)))
                    maturity_gap = abs(float(dte_a_arr[nearest_idx]) - float(dte_b))
                    if maturity_gap > max_maturity_gap:
                        continue

                    ln_a_interp = ln_price_at(curve_a, float(dte_b), max_extrap)
                    if ln_a_interp is None:
                        continue

                    gap_bps = 1e4 * (ln_a_interp - ln_b)
                    extrap = max(0.0, float(dte_b) - curve_a["dte"].max()) if float(dte_b) > curve_a["dte"].max() else max(0.0, curve_a["dte"].min() - float(dte_b))

                    liq_ok_a = not day_df[day_df["symbol"] == fam_a]["zero_vol"].all()
                    liq_ok_b = not row_b["zero_vol"]
                    stale = bool(row_b.get("stale", False))

                    records.append({
                        "date": date_val,
                        "fam_a": fam_a,
                        "fam_b": fam_b,
                        "expiry_b": row_b["expiry"],
                        "dte_b": dte_b,
                        "gap_bps": gap_bps,
                        "extrap_days": extrap,
                        "liq_ok_a": liq_ok_a,
                        "liq_ok_b": liq_ok_b,
                        "stale": stale,
                    })

    return pd.DataFrame(records)
