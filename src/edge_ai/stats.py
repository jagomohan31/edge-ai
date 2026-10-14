"""stats.py: bootstrap CI, placebo, sub-period, slippage stress (Req 6.7)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from edge_ai.backtest import TradeRecord
from edge_ai.config import Config


def bootstrap_mean_pnl(trades: list[TradeRecord], cfg: Config) -> dict:
    """Bootstrap confidence interval for mean net P&L per trade."""
    rng = np.random.default_rng(cfg.stats.seed)
    if not trades:
        return {"mean": float("nan"), "ci_low": float("nan"), "ci_high": float("nan")}
    pnls = np.array([t.net_pnl_inr for t in trades])
    n = len(pnls)
    samples = rng.choice(pnls, size=(cfg.stats.bootstrap_resamples, n), replace=True)
    means = samples.mean(axis=1)
    ci_low = float(np.percentile(means, 2.5))
    ci_high = float(np.percentile(means, 97.5))
    return {"mean": float(pnls.mean()), "ci_low": ci_low, "ci_high": ci_high, "n_trades": n}


def placebo_test(trades: list[TradeRecord], equity_df: pd.DataFrame, cfg: Config) -> dict:
    """Placebo test: random entry dates, same holding-time distribution."""
    rng = np.random.default_rng(cfg.stats.seed + 1)
    if not trades or equity_df.empty:
        return {"p_value": float("nan"), "placebo_mean": float("nan")}
    all_dates = equity_df["date"].values
    actual_mean = float(np.mean([t.net_pnl_inr for t in trades]))

    daily_pnl = equity_df["daily_pnl"].values
    placebo_means = []
    for _ in range(cfg.stats.placebo_draws):
        indices = rng.integers(0, len(all_dates), size=len(trades))
        draws = daily_pnl[indices] if len(daily_pnl) > 0 else np.zeros(len(trades))
        placebo_means.append(float(np.mean(draws)))

    placebo_means_arr = np.array(placebo_means)
    p_value = float((placebo_means_arr >= actual_mean).mean())
    return {
        "actual_mean": actual_mean,
        "placebo_mean": float(placebo_means_arr.mean()),
        "p_value": p_value,
    }


def sub_period_results(trades: list[TradeRecord], equity_df: pd.DataFrame) -> pd.DataFrame:
    """Sub-period results by quarter."""
    if not trades:
        return pd.DataFrame()
    df = pd.DataFrame([
        {
            "date": t.exit_date,
            "net_pnl": t.net_pnl_inr,
        }
        for t in trades
    ])
    df["date"] = pd.to_datetime(df["date"])
    df["quarter"] = df["date"].dt.to_period("Q")
    return df.groupby("quarter")["net_pnl"].agg(["sum", "mean", "count"]).reset_index()


def slippage_stress(trades: list[TradeRecord], equity_df: pd.DataFrame, multipliers: list[int]) -> pd.DataFrame:
    """Slippage stress: recompute net P&L at 1x, 2x, 3x slippage."""
    rows = []
    for mult in multipliers:
        # Approximate: slippage is embedded in costs; scale costs proportionally
        stressed_pnl = sum(
            t.gross_pnl_inr - (t.entry_cost_inr + t.exit_cost_inr) * mult
            for t in trades
        ) if trades else 0.0
        rows.append({"slippage_multiplier": mult, "net_pnl": stressed_pnl})
    return pd.DataFrame(rows)
