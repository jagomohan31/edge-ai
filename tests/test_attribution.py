from datetime import date

import pandas as pd

from edge_ai.attribution import compute_attribution
from edge_ai.config import load_config


def test_empty_trades_returns_zeros():
    cfg = load_config()
    equity = pd.DataFrame({"date": [date(2025, 1, 2)], "portfolio_value": [0.0], "daily_pnl": [0.0]})
    factor = pd.DataFrame({"date": [date(2025, 1, 2)], "G": [7000.0], "G_ret": [0.0]})
    panel = pd.DataFrame()
    result = compute_attribution([], equity, factor, panel, cfg)
    assert result["n_trades"] == 0
    assert result["gross_pnl"] == 0.0
    assert result["net_pnl"] == 0.0


def test_waterfall_components_present():
    cfg = load_config()
    equity = pd.DataFrame({"date": [], "portfolio_value": [], "daily_pnl": []})
    factor = pd.DataFrame({"date": [], "G": [], "G_ret": []})
    result = compute_attribution([], equity, factor, pd.DataFrame(), cfg)
    for key in ["gross_pnl", "gold_pnl", "total_costs", "net_pnl", "alpha", "beta", "n_trades"]:
        assert key in result, f"missing key: {key}"
