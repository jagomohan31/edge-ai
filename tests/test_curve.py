import math
from datetime import date

import numpy as np
import pandas as pd

from edge_ai.clean import clean
from edge_ai.config import load_config
from edge_ai.curve import compute_curves, compute_gold_factor
from edge_ai.synthetic import generate_bhavcopy


def _panel(cfg, start=date(2025, 1, 2), end=date(2025, 4, 30)):
    raw = generate_bhavcopy(start, end, cfg, inject_anomalies=False)
    df, _ = clean(raw, cfg)
    df["dte"] = (pd.to_datetime(df["expiry"]) - pd.to_datetime(df["date"])).dt.days
    sessions = sorted(df["date"].unique())
    df["session_idx"] = df["date"].map({d: i for i, d in enumerate(sessions)})
    df["ln_px_fine"] = np.log(df["px_g_fine"])
    return df


def test_curves_has_required_cols():
    cfg = load_config()
    panel = _panel(cfg)
    curves = compute_curves(panel, cfg)
    for col in ["date", "family", "expiry", "dte", "ln_px_fine", "traded"]:
        assert col in curves.columns, f"missing column: {col}"


def test_implied_carry_populated():
    cfg = load_config()
    panel = _panel(cfg)
    curves = compute_curves(panel, cfg)
    carry = curves["implied_carry_ann"].dropna()
    assert len(carry) > 0, "No implied_carry_ann values computed"


def test_gold_factor_positive():
    cfg = load_config()
    panel = _panel(cfg)
    curves = compute_curves(panel, cfg)
    factor = compute_gold_factor(curves, cfg)
    assert "G" in factor.columns
    assert "G_ret" in factor.columns
    valid = factor["G"].dropna()
    assert len(valid) > 0
    assert (valid > 0).all(), "Gold factor G must be positive"


def test_carry_formula():
    # c = 365 * ln(P2/P1) / (dte2 - dte1)
    # If P2 = P1 * exp(0.07 * 30/365), carry should be ~7%
    p1 = 700.0
    p2 = p1 * math.exp(0.07 * 30 / 365)
    carry = 365 * math.log(p2 / p1) / 30
    assert abs(carry - 0.07) < 1e-6
