"""attribution.py: P&L waterfall, gold-beta attribution (Req 6.5)."""
from __future__ import annotations

import pandas as pd
import statsmodels.api as sm

from edge_ai.backtest import TradeRecord
from edge_ai.config import Config


def compute_attribution(
    trades: list[TradeRecord],
    equity_df: pd.DataFrame,
    factor_df: pd.DataFrame,
    panel: pd.DataFrame,
    cfg: Config,
) -> dict:
    """Compute attribution: gross P&L, gold P&L, costs, net strategy P&L.

    Also runs OLS regression of daily strategy return on G_ret.
    Returns dict with waterfall components and regression stats.
    """
    if not trades:
        return {
            "gross_pnl": 0.0,
            "gold_pnl": 0.0,
            "total_costs": 0.0,
            "net_pnl": 0.0,
            "alpha": float("nan"),
            "beta": float("nan"),
            "alpha_se": float("nan"),
            "beta_se": float("nan"),
            "n_trades": 0,
        }

    gross = sum(t.gross_pnl_inr for t in trades)
    costs = sum(t.entry_cost_inr + t.exit_cost_inr for t in trades)
    net = sum(t.net_pnl_inr for t in trades)

    # Gold P&L: net fine-gram exposure * change in G
    # Approximate: use equity daily P&L regressed on G_ret
    merged = equity_df.merge(factor_df[["date", "G_ret"]], on="date", how="left")
    merged = merged.dropna(subset=["daily_pnl", "G_ret"])
    gold_pnl = float("nan")
    alpha = float("nan")
    beta = float("nan")
    alpha_se = float("nan")
    beta_se = float("nan")

    if len(merged) >= 10:
        y = merged["daily_pnl"].values
        x = sm.add_constant(merged["G_ret"].values)
        try:
            result = sm.OLS(y, x).fit()
            alpha = float(result.params[0])
            beta = float(result.params[1])
            alpha_se = float(result.bse[0])
            beta_se = float(result.bse[1])
            gold_pnl = float((merged["G_ret"] * beta).sum())
        except Exception:
            pass

    return {
        "gross_pnl": gross,
        "gold_pnl": gold_pnl,
        "total_costs": costs,
        "net_pnl": net,
        "alpha": alpha,
        "beta": beta,
        "alpha_se": alpha_se,
        "beta_se": beta_se,
        "n_trades": len(trades),
    }
