from datetime import date

import pandas as pd

from edge_ai.backtest import TradeRecord
from edge_ai.config import load_config
from edge_ai.stats import bootstrap_mean_pnl, slippage_stress, sub_period_results

_cfg = load_config()


def _make_trade(net_pnl: float) -> TradeRecord:
    return TradeRecord(
        trade_id="t1", entry_date=date(2025, 2, 1), exit_date=date(2025, 2, 6),
        fam_a="GOLDM", fam_b="GOLDTEN", expiry_b=date(2025, 3, 27),
        lots_a=2, lots_b=20,
        entry_px_a=7000.0, entry_px_b=700.0,
        exit_px_a=7010.0, exit_px_b=701.0,
        entry_cost_inr=100.0, exit_cost_inr=100.0,
        gross_pnl_inr=net_pnl + 200.0, net_pnl_inr=net_pnl,
        exit_reason="horizon", synthetic=True,
    )


def test_bootstrap_returns_ci():
    trades = [_make_trade(float(v)) for v in [100, 200, -50, 300, 150]]
    result = bootstrap_mean_pnl(trades, _cfg)
    assert "mean" in result
    assert result["ci_low"] <= result["mean"] <= result["ci_high"]


def test_bootstrap_empty():
    result = bootstrap_mean_pnl([], _cfg)
    assert result["mean"] != result["mean"]  # nan


def test_slippage_stress_increases_with_multiplier():
    trades = [_make_trade(500.0) for _ in range(5)]
    equity = pd.DataFrame({"date": [], "portfolio_value": [], "daily_pnl": []})
    df = slippage_stress(trades, equity, [1, 2, 3])
    pnls = df["net_pnl"].values
    assert pnls[0] >= pnls[1] >= pnls[2]


def test_sub_period_by_quarter():
    trades = [_make_trade(100.0) for _ in range(4)]
    equity = pd.DataFrame({"date": [], "portfolio_value": [], "daily_pnl": []})
    df = sub_period_results(trades, equity)
    assert "quarter" in df.columns
    assert "sum" in df.columns
