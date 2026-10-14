from datetime import date

import pandas as pd

from edge_ai.clean import clean
from edge_ai.config import load_config
from edge_ai.liquidity import calibrate_liquidity, liquidity_ok
from edge_ai.synthetic import generate_bhavcopy


def _panel(cfg):
    raw = generate_bhavcopy(date(2025, 1, 2), date(2025, 6, 30), cfg, inject_anomalies=False)
    df, _ = clean(raw, cfg)
    df["dte"] = (pd.to_datetime(df["expiry"]) - pd.to_datetime(df["date"])).dt.days
    sessions = sorted(df["date"].unique())
    df["session_idx"] = df["date"].map({d: i for i, d in enumerate(sessions)})
    return df


def test_calibrate_produces_thresholds():
    cfg = load_config()
    panel = _panel(cfg)
    dev_mask = panel["session_idx"] < int(len(panel["session_idx"].unique()) * 0.6)
    thresholds = calibrate_liquidity(panel, cfg, dev_mask)
    for sym in cfg.data.symbols:
        assert sym in thresholds
        assert "vol_g_min" in thresholds[sym]
        assert "oi_g_min" in thresholds[sym]


def test_liquidity_ok_passes_high_volume():
    cfg = load_config()
    row = pd.Series({"symbol": "GOLDM", "vol_g": 1e9, "oi_g": 1e9})
    thresholds = {"GOLDM": {"vol_g_min": 100.0, "oi_g_min": 100.0}}
    assert liquidity_ok(row, thresholds, cfg) is True


def test_liquidity_ok_fails_zero_volume():
    cfg = load_config()
    row = pd.Series({"symbol": "GOLDM", "vol_g": 0.0, "oi_g": 1e9})
    thresholds = {"GOLDM": {"vol_g_min": 100.0, "oi_g_min": 100.0}}
    assert liquidity_ok(row, thresholds, cfg) is False
