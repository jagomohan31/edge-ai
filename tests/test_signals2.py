"""tests/test_signals2.py: reference signal tests (no-lookahead, baseline, gates).

Ported from reference/test_ref.py.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from edge_ai.config import load_config
from edge_ai.signals import estimate_reversion_k, passes_gates, walk_forward_baseline

CFG = load_config()


def _obs(n_dates=200, seed=0):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2025-01-01", periods=n_dates)
    rows = [(d, k, rng.normal(0, 3)) for d in dates for k in ("A|0.0", "B|1.0")]
    return pd.DataFrame(rows, columns=["date", "key", "gap_bps"])


def test_walk_forward_baseline_has_no_lookahead():
    obs = _obs()
    a = walk_forward_baseline(obs, window=60, min_obs=20)
    cut = obs["date"].unique()[150]

    obs2 = obs.copy()
    obs2.loc[obs2["date"] > cut, "gap_bps"] += 100.0   # change only the FUTURE
    b = walk_forward_baseline(obs2, window=60, min_obs=20)

    past = a["date"] <= cut
    for col in ("baseline", "scale", "z"):
        assert np.allclose(
            a.loc[past, col].to_numpy(),
            b.loc[past, col].to_numpy(),
            equal_nan=True,
        ), f"lookahead detected in column: {col}"

    # not enough history yet at row 19 (0-indexed)
    day19 = obs["date"].unique()[19]
    day20 = obs["date"].unique()[20]
    assert a.loc[a["date"] == day19, "baseline"].isna().all()
    assert a.loc[a["date"] == day20, "baseline"].notna().all()


def test_baseline_uses_strictly_earlier_dates():
    obs = pd.DataFrame({
        "date": pd.bdate_range("2025-01-01", periods=30).repeat(2),
        "key": "K",
        "gap_bps": np.arange(60, dtype=float),
    })
    out = walk_forward_baseline(obs, window=60, min_obs=2)
    # day index 2 (3rd date): past data = rows for dates 0 and 1 -> gaps 0,1,2,3
    day3 = out[out["date"] == obs["date"].unique()[2]]
    assert day3["baseline"].iloc[0] == pytest.approx(np.median([0, 1, 2, 3]))


def test_estimate_reversion_k_on_ar1_series():
    rng = np.random.default_rng(1)
    rows = []
    for sid in range(3):
        x = 0.0
        for d in pd.bdate_range("2025-01-01", periods=400):
            x = 0.7 * x + rng.normal(0, 2)
            rows.append((d, f"s{sid}", f"k{sid}", x))
    obs = pd.DataFrame(rows, columns=["date", "series_id", "key", "gap_bps"])
    obs = walk_forward_baseline(obs, window=60, min_obs=20)
    k = estimate_reversion_k(obs, horizon=3, develop_end=obs["date"].max())
    assert 0.4 < k < 0.9, f"k={k} outside expected range for AR(1) phi=0.7"


def test_passes_gates_reports_first_failure():
    cfg_d = dict(
        z_threshold=2.0, min_net_edge_bps=2.0,
        delivery_cutoff_sessions=5, max_maturity_gap_days=7,
    )
    ok = dict(z=3.0, stale=False, liq_ok=True, sessions_to_expiry=20, leg_gap_days=3, net_edge_bps=4.0)
    assert passes_gates(ok, cfg_d) == (True, "")
    assert passes_gates({**ok, "z": 1.0}, cfg_d)[1]              == "z below threshold"
    assert passes_gates({**ok, "stale": True}, cfg_d)[1]         == "stale print"
    assert passes_gates({**ok, "liq_ok": False}, cfg_d)[1]       == "liquidity gate"
    assert passes_gates({**ok, "sessions_to_expiry": 6}, cfg_d)[1] == "inside delivery cutoff"
    assert passes_gates({**ok, "net_edge_bps": 1.0}, cfg_d)[1]  == "net edge below minimum"
