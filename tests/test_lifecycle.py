from datetime import date

import pandas as pd

from edge_ai.clean import clean
from edge_ai.config import load_config
from edge_ai.lifecycle import compute_lifecycle
from edge_ai.synthetic import generate_bhavcopy


def _panel(cfg):
    raw = generate_bhavcopy(date(2025, 1, 2), date(2025, 4, 30), cfg, inject_anomalies=False)
    df, _ = clean(raw, cfg)
    df["dte"] = (pd.to_datetime(df["expiry"]) - pd.to_datetime(df["date"])).dt.days
    return df


def test_lifecycle_has_required_cols():
    cfg = load_config()
    panel = _panel(cfg)
    lc = compute_lifecycle(panel, cfg)
    for col in ["symbol", "expiry", "first_seen", "delivery_cutoff_date"]:
        assert col in lc.columns, f"missing: {col}"


def test_delivery_cutoff_before_last_traded():
    cfg = load_config()
    panel = _panel(cfg)
    lc = compute_lifecycle(panel, cfg)
    valid = lc.dropna(subset=["last_traded", "delivery_cutoff_date"])
    for _, row in valid.iterrows():
        assert row["delivery_cutoff_date"] <= row["last_traded"], (
            f"cutoff {row['delivery_cutoff_date']} > last_traded {row['last_traded']}"
        )


def test_all_symbols_represented():
    cfg = load_config()
    panel = _panel(cfg)
    lc = compute_lifecycle(panel, cfg)
    for sym in cfg.data.symbols:
        assert sym in lc["symbol"].values, f"{sym} not in lifecycle"
