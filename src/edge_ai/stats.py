"""stats.py: bootstrap CI, placebo, sub-period, slippage stress (Req 6.7).

Reference: edge_ai_ref.py::bootstrap_ci, edge_ai_pipeline.py::placebo_means.
bootstrap_ci resamples trades (not days), seeded.
placebo_means runs actual simulated trades with random entries.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from edge_ai.config import Config


def bootstrap_ci(
    x,
    n: int = 10000,
    seed: int = 42,
    alpha: float = 0.05,
) -> tuple[float, float]:
    """CI of the mean net P&L per trade, resampling trades.  Seeded.

    Reference: edge_ai_ref.py::bootstrap_ci (exact copy).
    """
    x = np.asarray(x, float)
    rng = np.random.default_rng(seed)
    means = x[rng.integers(0, len(x), (n, len(x)))].mean(axis=1)
    lo = float(np.percentile(means, 100 * alpha / 2))
    hi = float(np.percentile(means, 100 * (1 - alpha / 2)))
    return lo, hi


def bootstrap_mean_pnl(trades: pd.DataFrame, cfg: Config) -> dict:
    """Convenience wrapper: bootstrap CI on net_inr column of trades DataFrame."""
    if trades is None or trades.empty:
        return {"mean": float("nan"), "ci_low": float("nan"), "ci_high": float("nan"), "n_trades": 0}
    x   = trades["net_inr"].to_numpy(float)
    lo, hi = bootstrap_ci(x, n=cfg.stats.bootstrap_resamples, seed=cfg.stats.seed)
    return {"mean": float(x.mean()), "ci_low": lo, "ci_high": hi, "n_trades": len(x)}


def placebo_means(
    g: pd.DataFrame,
    px: dict,
    pn: pd.DataFrame,
    cfg: Config,
    start,
    n_trades: int,
    holds: np.ndarray,
    draws: int = 200,
    seed: int = 42,
) -> np.ndarray:
    """Mean net P&L of random entries (same gates except z/net edge, same hold distribution).

    Reference: edge_ai_pipeline.py::placebo_means adapted to Config.
    """
    from edge_ai.backtest import legs_for, simulate_trade

    sessions = np.sort(pn["date"].unique())
    pool = g[
        (g["date"] > start) & g["liq_ok"]
        & (g["sessions_to_expiry"] > cfg.lifecycle.delivery_cutoff_sessions + 1)
        & g["baseline"].notna()
    ]
    rng      = np.random.default_rng(seed)
    z_series = {sid: d.set_index("date")["z"] for sid, d in g.groupby("series_id")}
    # never-revert config: exits only on horizon
    import copy
    cfg_ph = copy.deepcopy(cfg)
    cfg_ph.signals.exit_z  = -1.0
    cfg_ph.signals.stop_z  = 1e9

    out = []
    for _ in range(draws):
        pick = pool.iloc[rng.choice(len(pool), size=min(n_trades * 3, len(pool)), replace=False)]
        nets = []
        for row in pick.itertuples(index=False):
            h   = int(rng.choice(holds))
            cfg_h = copy.deepcopy(cfg_ph)
            cfg_h.signals.holding_horizon_sessions = h
            rd  = row._asdict()
            rd["dev"] = rd["dev"] if rng.random() < 0.5 else -rd["dev"]
            t = simulate_trade(
                px, legs_for(rd, cfg.backtest.basket_g, cfg),
                rd["date"], z_series[rd["series_id"]], sessions, cfg_h
            )
            if t is not None:
                nets.append(t["net_inr"])
            if len(nets) >= n_trades:
                break
        if nets:
            out.append(float(np.mean(nets)))
    return np.array(out)


def sub_period_results(trades: pd.DataFrame) -> pd.DataFrame:
    """Sub-period (quarterly) breakdown of net P&L."""
    if trades is None or trades.empty:
        return pd.DataFrame()
    df = trades[["exit_date", "net_inr"]].copy()
    df["exit_date"] = pd.to_datetime(df["exit_date"])
    df["quarter"]   = df["exit_date"].dt.to_period("Q")
    return df.groupby("quarter")["net_inr"].agg(["sum", "mean", "count"]).reset_index()


def slippage_stress(trades: pd.DataFrame, multipliers: list) -> pd.DataFrame:
    """Net P&L sensitivity to slippage cost multiplier.

    Approximate: re-scales the slippage portion of costs.
    Cost breakdown is not stored per trade, so we scale total cost.
    """
    if trades is None or trades.empty:
        return pd.DataFrame([{"slippage_multiplier": m, "net_pnl": 0.0} for m in multipliers])
    rows = []
    for m in multipliers:
        stressed = float((trades["gross_inr"] - trades["cost_inr"] * m).sum())
        rows.append({"slippage_multiplier": m, "net_pnl": stressed})
    return pd.DataFrame(rows)
