"""test_attribution.py: attribution module tests."""
import pandas as pd

from edge_ai.attribution import compute_attribution
from edge_ai.config import load_config

CFG = load_config()

def test_empty_trades_returns_zeros():
    r = compute_attribution(pd.DataFrame(), pd.DataFrame(), CFG)
    assert r["n_trades"] == 0
    assert r["gross"] == 0.0
    assert r["net"] == 0.0

def test_waterfall_keys_present():
    r = compute_attribution(pd.DataFrame(), pd.DataFrame(), CFG)
    for k in ["gross","gold","relative_value","costs","net","beta_fine_grams","beta_se","r2","n_trades"]:
        assert k in r, f"missing key: {k}"
