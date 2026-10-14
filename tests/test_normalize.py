import math

import pandas as pd

from edge_ai.normalize import ln_price_at


def test_ln_price_at_interpolation():
    curve = pd.DataFrame({"dte": [10.0, 20.0], "ln_px_fine": [0.0, 1.0]})
    val = ln_price_at(curve, 15.0, max_extrapolation_days=7)
    assert val is not None
    assert abs(val - 0.5) < 1e-9


def test_ln_price_at_extrapolation_within_limit():
    curve = pd.DataFrame({"dte": [10.0, 20.0], "ln_px_fine": [0.0, 1.0]})
    val = ln_price_at(curve, 25.0, max_extrapolation_days=7)
    assert val is not None


def test_ln_price_at_extrapolation_beyond_limit():
    curve = pd.DataFrame({"dte": [10.0, 20.0], "ln_px_fine": [0.0, 1.0]})
    val = ln_price_at(curve, 30.0, max_extrapolation_days=7)
    assert val is None


def test_ln_price_at_needs_two_points():
    curve = pd.DataFrame({"dte": [10.0], "ln_px_fine": [0.5]})
    val = ln_price_at(curve, 10.0, max_extrapolation_days=7)
    assert val is None


def test_gap_bps_formula():
    ln_a = math.log(1.0083)
    ln_b = 0.0
    gap = 1e4 * (ln_a - ln_b)
    assert abs(gap - 83.0) < 1.0, f"Expected ~83 bps, got {gap:.2f}"


def test_golden_purity_adjustment():
    px_g = 700.0
    px_g_fine_a = px_g / 0.995
    px_g_fine_b = px_g / 0.999
    gap = 1e4 * math.log(px_g_fine_a / px_g_fine_b)
    assert 35.0 < gap < 50.0, f"Purity gap {gap:.2f} bps not in expected range 35-50"
