"""test_signals.py: signal DataFrame field tests."""
import math

import numpy as np
import pandas as pd

from edge_ai.config import load_config
from edge_ai.normalize import build_gaps, normalize_panel
from edge_ai.signals import build_signals, find_alerts
from edge_ai.synthetic import make_synthetic_panel


def _pipeline(start="2025-01-02", end="2025-04-30", seed=1):
    cfg = load_config()
    panel = make_synthetic_panel(start=start, end=end, cfg=cfg, mode="noise_only", seed=seed)
    pn = normalize_panel(panel, cfg)
    sessions = np.sort(pn["date"].unique())
    dev_end = pd.Timestamp(sessions[int(0.6 * len(sessions)) - 1])
    gaps = build_gaps(pn, cfg)
    if gaps.empty:
        return None, None, sessions
    g = find_alerts(build_signals(gaps, pn, cfg, dev_end), cfg)
    return g, pn, sessions

def test_every_nonsignal_has_gate_reason():
    g, pn, _ = _pipeline()
    if g is None or g.empty:
        return
    blocked = g[~g["alert"]]
    for _, row in blocked.iterrows():
        assert row["blocked_by"] != "", "No-signal record missing gate explanation"

def test_required_columns_present():
    g, _, _ = _pipeline()
    if g is None or g.empty:
        return
    for col in ("date","alert","blocked_by","z","baseline","scale","net_edge_bps","k"):
        assert col in g.columns, f"missing column: {col}"

def test_first_session_has_no_valid_baseline():
    g, _, sessions = _pipeline(end="2025-01-31", seed=4)
    if g is None or g.empty:
        return
    first = sessions[0]
    for _, row in g[g["date"] == first].iterrows():
        assert math.isnan(row["z"]) or math.isnan(row["baseline"]), (
            "Expected nan baseline on first session, got z=" + str(row["z"]))

def test_no_lookahead_in_baseline():
    """Baselines at date t must use only data strictly before t."""
    import numpy as np

    from edge_ai.signals import walk_forward_baseline
    rng = np.random.default_rng(9)
    dates = pd.bdate_range("2025-01-01", periods=200)
    rows = [(d, "A|0.0", rng.normal(0, 3)) for d in dates]
    obs = pd.DataFrame(rows, columns=["date","key","gap_bps"])
    a = walk_forward_baseline(obs, window=60, min_obs=20)
    cut = obs["date"].unique()[150]
    obs2 = obs.copy()
    obs2.loc[obs2["date"] > cut, "gap_bps"] += 100.0
    b = walk_forward_baseline(obs2, window=60, min_obs=20)
    past = a["date"] <= cut
    assert np.allclose(a.loc[past,"baseline"].to_numpy(), b.loc[past,"baseline"].to_numpy(), equal_nan=True)
