import math
from datetime import date

import numpy as np
import pandas as pd

from edge_ai.clean import clean
from edge_ai.config import load_config
from edge_ai.normalize import compute_gaps
from edge_ai.signals import _dte_bucket, _robust_z, compute_signals
from edge_ai.synthetic import generate_bhavcopy


def test_dte_bucket():
    cfg = load_config()
    buckets = cfg.signals.dte_buckets
    assert _dte_bucket(3, buckets) == 0   # [0, 5)
    assert _dte_bucket(7, buckets) == 1   # [5, 10)
    assert _dte_bucket(15, buckets) == 2  # [10, 20)


def test_robust_z_basic():
    history = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    z, baseline, scale = _robust_z(2.5, history)
    assert not math.isnan(z)
    assert abs(baseline - 2.0) < 1e-6  # median of [0,1,2,3,4]
    assert scale > 0


def test_robust_z_empty_history():
    z, baseline, scale = _robust_z(1.0, np.array([]))
    assert math.isnan(z)


def test_every_nonsignal_has_gate_reason():
    # Every no-signal record must name the gate that blocked it.
    cfg = load_config()
    raw = generate_bhavcopy(date(2025, 1, 2), date(2025, 4, 30), cfg, inject_anomalies=False)
    df, _ = clean(raw, cfg)
    df["dte"] = (pd.to_datetime(df["expiry"]) - pd.to_datetime(df["date"])).dt.days
    sessions = sorted(df["date"].unique())
    df["session_idx"] = df["date"].map({d: i for i, d in enumerate(sessions)})
    gaps = compute_gaps(df, cfg)
    if gaps.empty:
        return
    sigs = compute_signals(gaps, df, cfg)
    for rec in sigs:
        if not rec.alert:
            assert rec.nearest_miss_gate != "", "No-signal record missing gate explanation"


def test_signal_record_fields():
    cfg = load_config()
    raw = generate_bhavcopy(date(2025, 1, 2), date(2025, 4, 30), cfg, inject_anomalies=False)
    df, _ = clean(raw, cfg)
    df["dte"] = (pd.to_datetime(df["expiry"]) - pd.to_datetime(df["date"])).dt.days
    sessions = sorted(df["date"].unique())
    df["session_idx"] = df["date"].map({d: i for i, d in enumerate(sessions)})
    gaps = compute_gaps(df, cfg)
    if gaps.empty:
        return
    sigs = compute_signals(gaps, df, cfg)
    assert len(sigs) > 0
    s = sigs[0]
    assert hasattr(s, "date")
    assert hasattr(s, "alert")
    assert hasattr(s, "nearest_miss_gate")


def test_no_future_data_in_baseline():
    # Baseline for session t must use only data strictly before t.
    # Verify: records at the very first date have nan z (no prior history).
    cfg = load_config()
    raw = generate_bhavcopy(date(2025, 1, 2), date(2025, 1, 31), cfg, inject_anomalies=False)
    df, _ = clean(raw, cfg)
    df["dte"] = (pd.to_datetime(df["expiry"]) - pd.to_datetime(df["date"])).dt.days
    sessions = sorted(df["date"].unique())
    df["session_idx"] = df["date"].map({d: i for i, d in enumerate(sessions)})
    gaps = compute_gaps(df, cfg)
    if gaps.empty:
        return
    sigs = compute_signals(gaps, df, cfg)
    first_date = sessions[0]
    first_day_sigs = [s for s in sigs if s.date == first_date]
    # The very first session has no prior history -- z must be nan
    for rec in first_day_sigs:
        assert math.isnan(rec.z), f"Expected nan z on first session, got {rec.z}"
