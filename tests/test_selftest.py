"""tests/test_selftest.py: 5 slow end-to-end self-tests on synthetic data.
Run with: pytest -m slow
Ported from reference/test_pipeline.py.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from edge_ai.attribution import attribute, gold_factor
from edge_ai.backtest import make_px, run_backtest
from edge_ai.config import load_config
from edge_ai.normalize import build_gaps, normalize_panel
from edge_ai.signals import build_signals, find_alerts
from edge_ai.stats import bootstrap_ci, placebo_means
from edge_ai.synthetic import make_synthetic_panel

pytestmark = pytest.mark.slow


def _run_all(mode: str, cfg=None, seed: int = 7):
    if cfg is None:
        cfg = load_config()
    panel = make_synthetic_panel(start="2025-01-01", end="2026-09-30", cfg=cfg, mode=mode, seed=seed)
    pn = normalize_panel(panel, cfg)
    sessions = np.sort(pn["date"].unique())
    dev_end = pd.Timestamp(sessions[int(0.6 * len(sessions)) - 1])
    gaps = build_gaps(pn, cfg)
    g = find_alerts(build_signals(gaps, pn, cfg, dev_end), cfg)
    px = make_px(pn)
    trades = run_backtest(g, px, pn, cfg, dev_end)
    return dict(panel=panel, pn=pn, gaps=gaps, g=g, px=px, trades=trades,
                sessions=sessions, dev_end=dev_end, cfg=cfg)


@pytest.fixture(scope="module")
def planted(): return _run_all("planted_edge")

@pytest.fixture(scope="module")
def noise(): return _run_all("noise_only")

@pytest.fixture(scope="module")
def noise_gate_off():
    cfg = load_config()
    cfg.signals.min_net_edge_bps = -1e9
    return _run_all("noise_only", cfg=cfg)


def test_noise_only_world_is_quiet(noise):
    g, tr = noise["g"], noise["trades"]
    oos = int(((g["alert"]) & (g["date"] > noise["dev_end"])).sum())
    assert oos <= 10, f"too many OOS alerts in noise world: {oos}"
    assert len(tr) <= 3, f"too many trades in noise world: {len(tr)}"


def test_noise_not_tradable_with_gate_off(noise_gate_off):
    tr = noise_gate_off["trades"]
    assert len(tr) >= 15, f"expected >=15 trades, got {len(tr)}"
    assert tr["net_inr"].mean() < 0
    assert tr["gross_inr"].mean() < 200
    lo, hi = bootstrap_ci(tr["net_inr"].to_numpy(), n=2000, seed=42)
    assert hi < 0, f"whole CI should be < 0; got ({lo:.0f}, {hi:.0f})"


def test_planted_edge_found_beats_placebo(planted):
    tr = planted["trades"]
    assert len(tr) >= 10
    assert tr["gross_inr"].mean() > 0
    assert tr["net_inr"].mean() > 0
    pl = placebo_means(
        planted["g"], planted["px"], planted["pn"], planted["cfg"],
        planted["dev_end"], n_trades=len(tr),
        holds=tr["hold_sessions"].to_numpy(), draws=40, seed=42,
    )
    assert len(pl) > 0
    assert tr["net_inr"].mean() > np.percentile(pl, 95)


def test_attribution_reconciles_gold_is_small(planted):
    tr = planted["trades"]
    G = gold_factor(planted["pn"], horizon=planted["cfg"].curve.gold_factor_horizon_days)
    a = attribute(tr, G)
    assert a["gross"] == pytest.approx(tr["gross_inr"].sum(), rel=1e-6)
    assert a["net"] == pytest.approx(a["gross"] - a["costs"], rel=1e-6)
    assert a["gross"] == pytest.approx(a["gold"] + a["relative_value"], rel=1e-6)
    assert abs(a["gold"]) < 0.2 * abs(a["gross"])


def test_signals_no_lookahead(planted):
    pn, cfg = planted["pn"], planted["cfg"]
    sessions = planted["sessions"]
    cut = pd.Timestamp(sessions[int(0.8 * len(sessions))])
    changed = pn[["date", "symbol", "expiry", "open", "high", "low", "close", "volume", "oi"]].copy()
    m = (changed["symbol"] == "GOLDPETAL") & (changed["date"] > cut)
    for c in ("open", "high", "low", "close"):
        changed.loc[m, c] = (changed.loc[m, c] * 1.01).round()
    pn2 = normalize_panel(changed, cfg)
    dev_end = planted["dev_end"]
    g1 = planted["g"]
    g2 = find_alerts(build_signals(build_gaps(pn2, cfg), pn2, cfg, dev_end), cfg)
    cols = ["gap_bps", "baseline", "z", "net_edge_bps", "k"]
    a = g1[g1["date"] <= cut].reset_index(drop=True)
    b = g2[g2["date"] <= cut].reset_index(drop=True)
    assert len(a) == len(b)
    for col in cols:
        assert np.allclose(a[col].to_numpy(float), b[col].to_numpy(float), equal_nan=True), col
    assert (a["alert"].to_numpy() == b["alert"].to_numpy()).all()
    later_a = g1[g1["date"] > cut]["gap_bps"].to_numpy()[:200]
    later_b = g2[g2["date"] > cut]["gap_bps"].to_numpy()[:200]
    assert not np.allclose(later_a, later_b, equal_nan=True)
