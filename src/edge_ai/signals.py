"""signals.py: robust z-score baselines, alerts, no-signal records (Req 5).

Reference implementations from edge_ai_ref.py / edge_ai_pipeline.py:
  mad_scale, walk_forward_baseline, estimate_reversion_k,
  passes_gates, build_signals, find_alerts.

Past-only: every baseline uses data strictly before the current date.
Quiet by default: every row has alert=True or alert=False + blocked_by reason.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from edge_ai.config import Config
from edge_ai.normalize import build_gaps

# ------------------------------------------------------------------ primitives

def mad_scale(h: np.ndarray) -> tuple[float, float]:
    """Return (median, 1.4826 * MAD).  Reference: edge_ai_ref.py::mad_scale."""
    med = float(np.median(h))
    return med, float(1.4826 * np.median(np.abs(h - med)))


def walk_forward_baseline(
    obs: pd.DataFrame,
    window: int = 60,
    min_obs: int = 20,
    floor_bps: float = 0.5,
) -> pd.DataFrame:
    """Add baseline, scale, z columns to obs using strictly past data.

    obs columns: date, key (pair + DTE bucket), gap_bps.
    For each row the baseline uses only observations of the same key on strictly
    earlier dates.  Reference: edge_ai_ref.py::walk_forward_baseline (exact copy).
    """
    obs = obs.sort_values("date").copy()
    base  = pd.Series(np.nan, index=obs.index)
    scale = pd.Series(np.nan, index=obs.index)
    for _, g in obs.groupby("key", sort=False):
        hist: list[float] = []
        for _, day in g.groupby("date", sort=True):
            h = np.asarray(hist[-window:])
            if len(h) >= min_obs:
                med, s = mad_scale(h)
                base.loc[day.index]  = med
                scale.loc[day.index] = max(s, floor_bps)
            hist.extend(day["gap_bps"].tolist())
    obs["baseline"] = base
    obs["scale"]    = scale
    obs["z"] = (obs["gap_bps"] - obs["baseline"]) / obs["scale"]
    return obs


def estimate_reversion_k(obs: pd.DataFrame, horizon: int, develop_end) -> float:
    """Fraction of the deviation that reverts within `horizon` observations.

    Estimated on the DEVELOP window only: k = -sum(dev*delta)/sum(dev^2),
    clipped to [0, 1].  obs needs series_id, date, gap_bps, baseline.
    Reference: edge_ai_ref.py::estimate_reversion_k (exact copy).
    """
    d = obs.sort_values(["series_id", "date"]).copy()
    d["delta"] = d.groupby("series_id")["gap_bps"].shift(-horizon) - d["gap_bps"]
    d["dev"]   = d["gap_bps"] - d["baseline"]
    d = d[d["date"] <= develop_end].dropna(subset=["delta", "dev"])
    if d.empty or (d["dev"] ** 2).sum() == 0:
        return 0.0
    return float(np.clip(-(d["dev"] * d["delta"]).sum() / (d["dev"] ** 2).sum(), 0.0, 1.0))


def passes_gates(row: dict, cfg_dict: dict) -> tuple[bool, str]:
    """First failing gate wins. Returns (passed, gate_name).

    row keys: z, net_edge_bps, liq_ok, sessions_to_expiry, stale, leg_gap_days.
    Reference: edge_ai_ref.py::passes_gates (exact copy).
    """
    if not np.isfinite(row["z"]) or abs(row["z"]) < cfg_dict["z_threshold"]:
        return False, "z below threshold"
    if row["stale"]:
        return False, "stale print"
    if not row["liq_ok"]:
        return False, "liquidity gate"
    if row["sessions_to_expiry"] <= cfg_dict["delivery_cutoff_sessions"] + 1:
        return False, "inside delivery cutoff"
    if row["leg_gap_days"] > cfg_dict["max_maturity_gap_days"]:
        return False, "maturity gap too large"
    if row["net_edge_bps"] < cfg_dict["min_net_edge_bps"]:
        return False, "net edge below minimum"
    return True, ""


def sessions_to_expiry(sessions: np.ndarray, t, expiry) -> int:
    """Number of sessions strictly after t up to and including expiry.

    Reference: edge_ai_ref.py::sessions_to_expiry (exact copy).
    """
    s = pd.to_datetime(sessions).to_numpy()
    return int(
        np.searchsorted(s, np.datetime64(pd.Timestamp(expiry)), side="right")
        - np.searchsorted(s, np.datetime64(pd.Timestamp(t)), side="right")
    )


# ------------------------------------------------------------------ pipeline helpers

def _round_trip_cost_bps(
    fam_a: str, px_a: float,
    fam_b: str, px_b: float,
    cfg: Config,
    stress: float = 1.0,
) -> float:
    """Round-trip cost as bps of leg-A notional (entry+exit, both legs).

    Reference: edge_ai_pipeline.py::round_trip_cost_bps adapted to Config.
    """
    from edge_ai.costs import cost_per_leg
    basket_g   = cfg.backtest.basket_g
    ca         = cfg.contracts[fam_a]
    cb         = cfg.contracts[fam_b]
    lots_a     = basket_g // ca.lot_g
    lots_b     = basket_g // cb.lot_g
    notional_a = px_a * ca.lot_g / ca.quote_g * lots_a

    total = sum(
        cost_per_leg(px, lots, sym, side, cfg, stress)["total_inr"]
        for sym, px, lots, side in [
            (fam_a, px_a, lots_a, "sell"),
            (fam_b, px_b, lots_b, "buy"),
            (fam_a, px_a, lots_a, "buy"),
            (fam_b, px_b, lots_b, "sell"),
        ]
    )
    return 1e4 * total / notional_a if notional_a > 0 else float("nan")


def _past_only_liquidity_thresholds(pn: pd.DataFrame, q: float = 0.25, min_rows: int = 60) -> dict:
    """q-quantile of traded grams per (date, symbol) using STRICTLY earlier dates.

    NaN until min_rows rows exist -- prevents look-ahead and handles GOLDTEN's short history.
    Reference: edge_ai_pipeline.py::past_only_liquidity_thresholds (exact copy).
    """
    import bisect
    hist: dict[str, list] = {s: [] for s in pn["symbol"].unique()}
    out: dict = {}
    for d, day in pn.groupby("date", sort=True):
        for s, h in hist.items():
            out[(d, s)] = h[int(q * (len(h) - 1))] if len(h) >= min_rows else np.nan
        for s, v in zip(day.loc[day["traded"], "symbol"], day.loc[day["traded"], "vol_g"], strict=False):
            bisect.insort(hist[s], float(v))
    return out


def _split_sessions(sessions, cfg: Config):
    """Return (develop_end date) for the develop window (60% of sessions)."""
    n = len(sessions)
    develop_end = pd.Timestamp(sessions[int(0.6 * n) - 1])
    return develop_end


# ------------------------------------------------------------------ main pipeline

def build_signals(gaps: pd.DataFrame, pn: pd.DataFrame, cfg: Config, develop_end) -> pd.DataFrame:
    """Add baseline, k, expected_conv_bps, cost_bps, net_edge_bps, liq_ok, sessions_to_expiry.

    Uses past-only baselines and past-only liquidity thresholds.
    Reference: edge_ai_pipeline.py::build_signals adapted to Config.
    """
    p = cfg.signals
    g = gaps.copy()
    g["pair"]      = g["fam_a"] + "/" + g["fam_b"]
    g["bucket"]    = pd.cut(
        g["dte_b"], p.dte_buckets, right=False, labels=False
    ).astype(float)
    g["key"]       = g["pair"] + "|" + g["bucket"].astype(str)
    g["series_id"] = g["pair"] + "|" + g["expiry_b"].dt.strftime("%Y%m%d")

    g = walk_forward_baseline(g, p.baseline_window, p.min_obs, p.floor_bps)

    k = estimate_reversion_k(g, p.holding_horizon_sessions, develop_end)
    g["dev"]              = g["gap_bps"] - g["baseline"]
    g["expected_conv_bps"] = k * g["dev"].abs()
    g["cost_bps"] = [
        _round_trip_cost_bps(a, pa, b, pb, cfg)
        for a, pa, b, pb in zip(g["fam_a"], g["px_a"], g["fam_b"], g["px_b"], strict=False)
    ]
    g["net_edge_bps"] = g["expected_conv_bps"] - g["cost_bps"]
    g["k"] = k

    thr = _past_only_liquidity_thresholds(
        pn, cfg.liquidity.min_traded_g_quantile, cfg.liquidity.liq_min_rows
    )
    g["thr_a"] = [thr.get((d, s), np.nan) for d, s in zip(g["date"], g["fam_a"], strict=False)]
    g["thr_b"] = [thr.get((d, s), np.nan) for d, s in zip(g["date"], g["fam_b"], strict=False)]
    g["liq_ok"] = (g["vol_g_a"] >= g["thr_a"]) & (g["vol_g_b"] >= g["thr_b"])

    sessions_arr = np.sort(pn["date"].unique())
    g["sessions_to_expiry"] = [
        min(sessions_to_expiry(sessions_arr, d, ea),
            sessions_to_expiry(sessions_arr, d, eb))
        for d, ea, eb in zip(g["date"], g["expiry_a"], g["expiry_b"], strict=False)
    ]

    if "stale" not in g.columns:
        g["stale"] = False

    return g.sort_values(["date", "series_id"]).reset_index(drop=True)


def find_alerts(g: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Apply gates + per-series cooldown.  Returns g with alert and blocked_by columns.

    Reference: edge_ai_pipeline.py::find_alerts adapted to Config.
    """
    p = cfg.signals
    cfg_dict = dict(
        z_threshold=p.z_threshold,
        min_net_edge_bps=p.min_net_edge_bps,
        delivery_cutoff_sessions=cfg.lifecycle.delivery_cutoff_sessions,
        max_maturity_gap_days=p.max_maturity_gap_days,
    )
    keep, reasons = [], []
    sess_idx = {d: i for i, d in enumerate(np.sort(g["date"].unique()))}
    last: dict[str, int] = {}
    for row in g.itertuples(index=False):
        ok, why = passes_gates(row._asdict(), cfg_dict)
        sid = row.series_id
        i   = sess_idx[row.date]
        if ok and sid in last and (i - last[sid]) < p.cooldown_sessions:
            ok, why = False, "cooldown"
        if ok:
            last[sid] = i
        keep.append(ok)
        reasons.append(why)
    out = g.copy()
    out["alert"]      = keep
    out["blocked_by"] = reasons
    return out


def compute_signals(pn: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Convenience wrapper: gaps -> build_signals -> find_alerts.

    Returns the full signal DataFrame with alert column.
    """
    sessions_arr = np.sort(pn["date"].unique())
    develop_end  = pd.Timestamp(sessions_arr[int(0.6 * len(sessions_arr)) - 1])
    gaps = build_gaps(pn, cfg)
    if gaps.empty:
        return pd.DataFrame()
    g = build_signals(gaps, pn, cfg, develop_end)
    return find_alerts(g, cfg)
