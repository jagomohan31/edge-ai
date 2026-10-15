"""attribution.py: P&L waterfall, gold-factor attribution, beta regression (Req 6.5).

Reference: edge_ai_pipeline.py::attribute, gold_factor.
Gross = gold-price P&L + relative-value P&L.  Costs are separate.
Returns beta_se (standard error of the beta), which must be reported.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from edge_ai.config import Config
from edge_ai.normalize import ln_price_at


def gold_factor(
    pn: pd.DataFrame,
    family: str = "GOLDM",
    horizon: int = 30,
    max_gap: float = 40.0,
) -> pd.Series:
    """Constant-maturity gold factor G (INR per fine gram at `horizon` days).

    Uses ln interpolation along the GOLDM curve, forward-filled.
    Reference: edge_ai_pipeline.py::gold_factor (exact copy).
    """
    out = {}
    for d, day in pn[(pn["symbol"] == family) & pn["traded"]].groupby("date"):
        v = ln_price_at(day, horizon, max_gap)
        out[d] = math.exp(v) if np.isfinite(v) else np.nan
    return pd.Series(out).sort_index().ffill()


def attribute(trades: pd.DataFrame, G: pd.Series) -> dict:
    """Compute waterfall: gross -> gold-price P&L + relative-value P&L; costs; net.

    Also runs a beta regression of daily strategy returns on gold's return, returning
    beta_fine_grams, beta_se, and r-squared.

    Each trade must have a 'daily' column containing a list of (date, pnl) tuples,
    an 'exposure_g' column (net fine grams), 'gross_inr', 'cost_inr', 'net_inr'.

    Reference: edge_ai_pipeline.py::attribute (exact copy).
    """
    dG = G.diff()
    daily_total: dict = {}
    daily_gold:  dict = {}

    for t in trades.itertuples(index=False):
        for d, pnl in t.daily:
            daily_total[d] = daily_total.get(d, 0.0) + pnl
            dg = dG.get(d, 0.0)
            dg = float(dg) if np.isfinite(dg) else 0.0
            daily_gold[d]  = daily_gold.get(d, 0.0)  + t.exposure_g * dg

    idx  = sorted(daily_total)
    tot  = pd.Series(daily_total).reindex(idx)
    gold = pd.Series(daily_gold).reindex(idx)

    # OLS regression of daily strategy P&L on gold factor return
    x    = dG.reindex(idx).fillna(0.0).to_numpy()
    beta = 0.0
    se   = float("nan")
    r2   = 0.0
    if np.var(x) > 0 and len(x) > 2:
        beta = float(np.cov(tot.to_numpy(), x)[0, 1] / np.var(x, ddof=1))
        resid = tot.to_numpy() - tot.mean() - beta * (x - x.mean())
        s2    = resid @ resid / max(len(x) - 2, 1)
        cov22 = s2 / ((x - x.mean()) @ (x - x.mean()))
        se    = float(math.sqrt(cov22)) if cov22 >= 0 else float("nan")
        ss_res = float(resid @ resid)
        ss_tot = float((tot - tot.mean()) @ (tot - tot.mean()))
        r2   = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    return dict(
        gross=float(tot.sum()),
        gold=float(gold.sum()),
        relative_value=float(tot.sum() - gold.sum()),
        costs=float(trades["cost_inr"].sum()),
        net=float(trades["net_inr"].sum()),
        beta_fine_grams=beta,
        beta_se=se,
        r2=r2,
    )


def compute_attribution(trades: pd.DataFrame, pn: pd.DataFrame, cfg: Config) -> dict:
    """Convenience wrapper: compute gold_factor from panel, then attribute."""
    if trades is None or trades.empty:
        return dict(
            gross=0.0, gold=0.0, relative_value=0.0, costs=0.0, net=0.0,
            beta_fine_grams=0.0, beta_se=float("nan"), r2=0.0, n_trades=0,
        )
    G = gold_factor(pn, horizon=cfg.curve.gold_factor_horizon_days)
    result = attribute(trades, G)
    result["n_trades"] = len(trades)
    return result
