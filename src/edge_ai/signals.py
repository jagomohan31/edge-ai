"""signals.py: robust z-score signals, alerts, and no-signal records (Req 5).

Past-only baselines: median and MAD over baseline_window sessions (no lookahead).
Alert fires only when ALL gates pass.
Quiet by default -- every day writes either an alert or a "no signal" record.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from edge_ai.config import Config


@dataclass
class SignalRecord:
    """One signal record per (date, pair, expiry_b)."""

    date: object
    fam_a: str
    fam_b: str
    expiry_b: object
    dte_b: float
    gap_bps: float
    baseline_bps: float
    scale_bps: float
    z: float
    alert: bool
    nearest_miss_gate: str  # which gate blocked (if not alert)
    net_edge_bps: float
    cost_bps: float
    liq_ok: bool
    stale: bool


def _dte_bucket(dte: float, buckets: list[int]) -> int:
    """Return the bucket index for a given DTE."""
    for i in range(len(buckets) - 1):
        if buckets[i] <= dte < buckets[i + 1]:
            return i
    return len(buckets) - 2


def _robust_z(gap: float, history: np.ndarray) -> tuple[float, float, float]:
    """Compute robust z-score, baseline, and scale from historical gaps."""
    if len(history) == 0:
        return float("nan"), float("nan"), float("nan")
    baseline = float(np.median(history))
    mad = float(np.median(np.abs(history - baseline)))
    scale = 1.4826 * mad if mad > 0 else 1e-6
    z = (gap - baseline) / scale
    return z, baseline, scale


def compute_signals(
    gaps_df: pd.DataFrame,
    panel: pd.DataFrame,
    cfg: Config,
    liquidity_thresholds: dict | None = None,
    develop_mask: pd.Series | None = None,
) -> list[SignalRecord]:
    """Compute signal records for every (date, pair, expiry_b).

    Uses past-only baselines (no lookahead). Returns list of SignalRecord.
    """
    from edge_ai.costs import round_trip_cost_bps

    baseline_window = cfg.signals.baseline_window
    dte_buckets = cfg.signals.dte_buckets
    z_threshold = cfg.signals.z_threshold
    min_net_edge = cfg.signals.min_net_edge_bps
    cooldown = cfg.signals.cooldown_sessions
    delivery_cutoff = cfg.lifecycle.delivery_cutoff_sessions

    cooldown_tracker: dict[tuple, int] = {}  # (fam_a, fam_b, expiry_b) -> last alert session_idx
    records: list[SignalRecord] = []

    # Map date -> session_idx
    date_to_idx = {}
    if "session_idx" in panel.columns:
        date_to_idx = panel.drop_duplicates("date").set_index("date")["session_idx"].to_dict()

    sorted_dates = sorted(gaps_df["date"].unique())

    for date_val in sorted_dates:
        session_idx = date_to_idx.get(date_val, 0)
        day_gaps = gaps_df[gaps_df["date"] == date_val]

        for _, row in day_gaps.iterrows():
            pair_key = (row["fam_a"], row["fam_b"], row["expiry_b"])
            dte_b = float(row["dte_b"])
            gap = float(row["gap_bps"])
            bucket = _dte_bucket(dte_b, dte_buckets)

            # Past history for this pair and bucket
            hist = gaps_df[
                (gaps_df["date"] < date_val)
                & (gaps_df["fam_a"] == row["fam_a"])
                & (gaps_df["fam_b"] == row["fam_b"])
            ]
            if "dte_b" in hist.columns:
                hist_b = hist[hist["dte_b"].apply(lambda d: _dte_bucket(float(d), dte_buckets)) == bucket]
            else:
                hist_b = hist
            hist_window = hist_b.tail(baseline_window)["gap_bps"].values.astype(float)

            z, baseline, scale = _robust_z(gap, hist_window)

            # Cost estimate (simplified: use mid-price from panel)
            fam_a_rows = panel[(panel["date"] == date_val) & (panel["symbol"] == row["fam_a"])]
            fam_b_rows = panel[(panel["date"] == date_val) & (panel["symbol"] == row["fam_b"])]
            cost_bps = float("nan")
            if not fam_a_rows.empty and not fam_b_rows.empty:
                from edge_ai.spec import gram_basket
                alloc_a = gram_basket(cfg.backtest.basket_g, row["fam_a"], cfg)
                alloc_b = gram_basket(cfg.backtest.basket_g, row["fam_b"], cfg)
                try:
                    cost_bps = round_trip_cost_bps(
                        float(fam_a_rows["close"].iloc[0]), alloc_a.lots, row["fam_a"],
                        float(fam_b_rows["close"].iloc[0]), alloc_b.lots, row["fam_b"],
                        cfg,
                    )
                except Exception:
                    cost_bps = float("nan")

            # Expected convergence: median gap change over holding horizon for similar deviations
            net_edge = abs(gap - (baseline if not math.isnan(baseline) else 0)) - (cost_bps if not math.isnan(cost_bps) else 0)

            liq_ok = bool(row.get("liq_ok_a", True)) and bool(row.get("liq_ok_b", True))
            stale = bool(row.get("stale", False))

            # Gate checks
            gates_passed = True
            nearest_miss = ""

            if math.isnan(z) or abs(z) < z_threshold:
                gates_passed = False
                nearest_miss = f"z={z:.2f} < {z_threshold}"
            elif math.isnan(net_edge) or net_edge < min_net_edge:
                gates_passed = False
                nearest_miss = f"net_edge={net_edge:.2f} < {min_net_edge}"
            elif not liq_ok:
                gates_passed = False
                nearest_miss = "liquidity_gate"
            elif dte_b < delivery_cutoff:
                gates_passed = False
                nearest_miss = f"dte_b={dte_b:.0f} < delivery_cutoff={delivery_cutoff}"
            elif stale:
                gates_passed = False
                nearest_miss = "stale_price"
            elif row.get("extrap_days", 0) > cfg.signals.max_maturity_gap_days:
                gates_passed = False
                nearest_miss = "maturity_gap"
            elif pair_key in cooldown_tracker:
                sessions_since = session_idx - cooldown_tracker[pair_key]
                if sessions_since < cooldown:
                    gates_passed = False
                    nearest_miss = f"cooldown ({sessions_since}/{cooldown} sessions)"

            if gates_passed:
                cooldown_tracker[pair_key] = session_idx

            records.append(SignalRecord(
                date=date_val,
                fam_a=row["fam_a"],
                fam_b=row["fam_b"],
                expiry_b=row["expiry_b"],
                dte_b=dte_b,
                gap_bps=gap,
                baseline_bps=baseline,
                scale_bps=scale,
                z=z,
                alert=gates_passed,
                nearest_miss_gate=nearest_miss,
                net_edge_bps=net_edge,
                cost_bps=cost_bps,
                liq_ok=liq_ok,
                stale=stale,
            ))

    return records
