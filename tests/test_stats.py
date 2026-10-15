"""test_stats.py: stats module tests."""
import numpy as np
import pandas as pd

from edge_ai.config import load_config
from edge_ai.stats import bootstrap_ci, bootstrap_mean_pnl, slippage_stress, sub_period_results

CFG = load_config()

def _trades(nets):
    rows = []
    for i, net in enumerate(nets):
        rows.append({
            "net_inr": float(net), "gross_inr": float(net) + 200.0, "cost_inr": 200.0,
            "exit_date": pd.Timestamp("2025-02-01") + pd.Timedelta(days=i * 5),
            "hold_sessions": 3,
        })
    return pd.DataFrame(rows)

def test_bootstrap_ci_seeded():
    x = np.random.default_rng(3).normal(5, 2, 200)
    lo, hi = bootstrap_ci(x, n=2000, seed=7)
    assert lo < x.mean() < hi
    assert (lo, hi) == bootstrap_ci(x, n=2000, seed=7)
    assert bootstrap_ci([4.0, 4.0, 4.0], n=100) == (4.0, 4.0)

def test_bootstrap_mean_pnl_brackets_mean():
    trades = _trades([100, 200, -50, 300, 150])
    r = bootstrap_mean_pnl(trades, CFG)
    assert r["ci_low"] <= r["mean"] <= r["ci_high"]

def test_bootstrap_mean_pnl_empty():
    r = bootstrap_mean_pnl(pd.DataFrame(), CFG)
    assert r["n_trades"] == 0

def test_slippage_stress_increases():
    trades = _trades([500.0] * 5)
    df = slippage_stress(trades, [1, 2, 3])
    pnls = df["net_pnl"].values
    assert pnls[0] >= pnls[1] >= pnls[2]

def test_sub_period_has_quarter_column():
    trades = _trades([100.0] * 4)
    df = sub_period_results(trades)
    assert "quarter" in df.columns and "sum" in df.columns
