"""test_curve.py: curve and gold factor tests."""
import math

from edge_ai.config import load_config
from edge_ai.curve import compute_curves, compute_gold_factor
from edge_ai.normalize import normalize_panel
from edge_ai.synthetic import make_synthetic_panel


def _panel():
    cfg = load_config()
    panel = make_synthetic_panel(start="2025-01-02", end="2025-04-30", cfg=cfg, mode="noise_only", seed=1)
    return normalize_panel(panel, cfg), cfg

def test_curves_has_required_cols():
    pn, cfg = _panel()
    curves = compute_curves(pn, cfg)
    for col in ["date","family","expiry","dte","ln_px_fine","traded"]:
        assert col in curves.columns

def test_implied_carry_populated():
    pn, cfg = _panel()
    curves = compute_curves(pn, cfg)
    assert len(curves["implied_carry_ann"].dropna()) > 0

def test_gold_factor_positive():
    pn, cfg = _panel()
    curves = compute_curves(pn, cfg)
    factor = compute_gold_factor(curves, cfg)
    assert "G" in factor.columns
    valid = factor["G"].dropna()
    assert len(valid) > 0
    assert (valid > 0).all()

def test_carry_formula():
    p1 = 700.0
    p2 = p1 * math.exp(0.07 * 30 / 365)
    carry = 365 * math.log(p2 / p1) / 30
    assert abs(carry - 0.07) < 1e-6
