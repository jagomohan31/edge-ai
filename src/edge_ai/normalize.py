"""normalize.py: price per fine gram, maturity-matched parity gaps (Req 3).

Reference implementations from edge_ai_ref.py: normalize_panel, ln_price_at,
parity_row, build_gaps.  These are the exact reference functions adapted to use
the Config object instead of the CONTRACTS dict.

Golden test: 83 bps naive -> 40.1 bps purity + 51.8 bps maturity + (-8.9) bps residual.
Identity: naive_bps == purity_bps + maturity_bps + gap_bps  (exact, by construction).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from edge_ai.config import Config

# Canonical pair list: (A smaller/newer family, B larger/older family)
PAIRS = [
    ("GOLDTEN",    "GOLDM"),
    ("GOLDGUINEA", "GOLDM"),
    ("GOLDPETAL",  "GOLDM"),
    ("GOLDGUINEA", "GOLDTEN"),
    ("GOLDPETAL",  "GOLDTEN"),
    ("GOLDPETAL",  "GOLDGUINEA"),
]


def normalize_panel(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Add normalised columns to the raw panel.

    Adds: lot_g, quote_g, fineness, dte, px_g, px_g_fine, vol_g, oi_g, traded, ln_px_fine,
    zero_vol, stale (stub -- always False until real stale detection is implemented).
    """
    contracts = cfg.contracts
    rows = df.copy()

    lot_g     = rows["symbol"].map({s: c.lot_g    for s, c in contracts.items()})
    quote_g   = rows["symbol"].map({s: c.quote_g  for s, c in contracts.items()})
    fineness  = rows["symbol"].map({s: c.fineness for s, c in contracts.items()})

    rows["lot_g"]      = lot_g
    rows["quote_g"]    = quote_g
    rows["fineness"]   = fineness
    rows["dte"]        = (rows["expiry"] - rows["date"]).dt.days.astype(int)
    rows["px_g"]       = rows["close"] / rows["quote_g"]           # INR per quoted gram
    rows["px_g_fine"]  = rows["px_g"] / rows["fineness"]           # INR per fine gram
    rows["vol_g"]      = rows["volume"] * rows["lot_g"]            # traded grams
    rows["oi_g"]       = rows["oi"]     * rows["lot_g"]
    rows["traded"]     = rows["volume"] > 0
    rows["ln_px_fine"] = np.log(rows["px_g_fine"])
    rows["zero_vol"]   = rows["volume"] == 0
    rows["stale"]      = False   # TODO: implement unchanged-close-while-neighbours-moved

    return rows


def ln_price_at(curve: pd.DataFrame, target_dte: float, max_gap: float = 7.0) -> float:
    """Interpolate ln(px_g_fine) along DTE for ONE family on ONE date.

    curve: rows with columns dte, px_g_fine (traded expiries of one family, one date).
    Extrapolates at most max_gap days beyond the observed range; returns nan otherwise.
    Reference: edge_ai_ref.py::ln_price_at (exact copy, parameter name aligned).
    """
    c = curve.sort_values("dte")
    x = c["dte"].to_numpy(float)
    y = np.log(c["px_g_fine"].to_numpy(float))
    if len(x) < 2:
        return np.nan
    if x[0] <= target_dte <= x[-1]:
        return float(np.interp(target_dte, x, y))
    # Extrapolation: use the near-end slope
    k, j = (0, 1) if target_dte < x[0] else (-1, -2)
    if abs(target_dte - x[k]) > max_gap:
        return np.nan
    return float(y[k] + (y[k] - y[j]) / (x[k] - x[j]) * (target_dte - x[k]))


def parity_row(
    day: pd.DataFrame,
    fam_a: str,
    fam_b: str,
    expiry_b,
    max_leg_gap_days: int = 7,
    max_extrap_days: float = 7.0,
):
    """Gap of family A vs ONE contract of family B, decomposed into purity/maturity/residual.

    naive = purity + maturity + residual  (exact identity, no rounding).
    gap_bps = residual = the carry-adjusted, purity-adjusted relative-value gap.

    Returns None if the gap cannot be computed (not enough traded expiries in A,
    or the nearest A expiry is too far from expiry_b, or extrapolation limit exceeded).

    Reference: edge_ai_ref.py::parity_row (exact copy).
    """
    b_rows = day[(day["symbol"] == fam_b) & (day["expiry"] == expiry_b) & day["traded"]]
    a_all  = day[(day["symbol"] == fam_a) & day["traded"]]
    if b_rows.empty or len(a_all) < 2:
        return None
    b = b_rows.iloc[0]
    gaps = (a_all["expiry"] - expiry_b).abs().dt.days
    if gaps.min() > max_leg_gap_days:
        return None
    leg = a_all.loc[gaps.idxmin()]                        # tradable A contract nearest to B expiry
    ln_a_at_b = ln_price_at(a_all, float(b["dte"]), max_extrap_days)
    if np.isnan(ln_a_at_b):
        return None
    naive    = 1e4 * np.log(leg["px_g"]      / b["px_g"])
    purity   = 1e4 * np.log(leg["fineness"]  / b["fineness"])
    maturity = 1e4 * (np.log(leg["px_g_fine"]) - ln_a_at_b)
    resid    = 1e4 * (ln_a_at_b - np.log(b["px_g_fine"]))
    return dict(
        date=b["date"], fam_a=fam_a, fam_b=fam_b,
        expiry_a=leg["expiry"], expiry_b=expiry_b,
        dte_a=int(leg["dte"]), dte_b=int(b["dte"]),
        naive_bps=float(naive), purity_bps=float(purity),
        maturity_bps=float(maturity), gap_bps=float(resid),
        px_a=float(leg["close"]), px_b=float(b["close"]),
        vol_g_a=float(leg["vol_g"]), vol_g_b=float(b["vol_g"]),
        leg_gap_days=int(abs((leg["expiry"] - expiry_b).days)),
        liq_ok_a=bool(leg["traded"]), liq_ok_b=bool(b["traded"]),
        stale=bool(b["stale"]),
    )


def build_gaps(pn: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Build one parity row per (date, pair, B expiry) across all configured pairs.

    Uses the canonical PAIRS list.  Returns a DataFrame with columns from parity_row
    plus computed extras used downstream by signals.
    """
    max_leg_gap = cfg.signals.max_maturity_gap_days
    max_extrap  = cfg.curve.max_extrapolation_days
    out = []
    for _, day in pn.groupby("date", sort=True):
        for fam_a, fam_b in PAIRS:
            # Skip pairs where either family has no data on this date
            b_expiries = day.loc[(day["symbol"] == fam_b) & day["traded"], "expiry"].unique()
            for expiry_b in b_expiries:
                r = parity_row(day, fam_a, fam_b, expiry_b, max_leg_gap, max_extrap)
                if r is not None:
                    out.append(r)
    return pd.DataFrame(out) if out else pd.DataFrame()
