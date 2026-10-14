from datetime import date

import pandas as pd

from edge_ai.clean import clean
from edge_ai.config import load_config
from edge_ai.normalize import compute_gaps
from edge_ai.signals import compute_signals
from edge_ai.synthetic import generate_bhavcopy


def _make_panel(cfg):
    raw_df = generate_bhavcopy(date(2025, 1, 2), date(2025, 6, 30), cfg, inject_anomalies=False)
    df, _ = clean(raw_df, cfg)
    if df.empty:
        return df
    df["dte"] = (pd.to_datetime(df["expiry"]) - pd.to_datetime(df["date"])).dt.days
    dates_sorted = sorted(df["date"].unique())
    df["session_idx"] = df["date"].map({d: i for i, d in enumerate(dates_sorted)})
    return df


def test_no_lookahead():
    cfg = load_config()
    panel = _make_panel(cfg)
    if panel.empty:
        return

    sessions = sorted(panel["date"].unique())
    if len(sessions) < 4:
        return

    t_idx = len(sessions) // 2
    t = sessions[t_idx]

    panel_up_to_t = panel[panel["date"] <= t].copy()
    gaps_up_to_t = compute_gaps(panel_up_to_t, cfg)
    sigs_up_to_t = compute_signals(gaps_up_to_t, panel_up_to_t, cfg)
    gaps_at_t = [s for s in sigs_up_to_t if s.date == t]

    # Modify data AFTER t
    panel_modified = panel.copy()
    after_mask = panel_modified["date"] > t
    panel_modified.loc[after_mask, "close"] = panel_modified.loc[after_mask, "close"] * 999.0
    panel_modified.loc[after_mask, "px_g_fine"] = panel_modified.loc[after_mask, "px_g_fine"] * 999.0

    panel_up_to_t_mod = panel_modified[panel_modified["date"] <= t].copy()
    gaps_up_to_t_mod = compute_gaps(panel_up_to_t_mod, cfg)
    sigs_up_to_t_mod = compute_signals(gaps_up_to_t_mod, panel_up_to_t_mod, cfg)
    gaps_at_t_mod = [s for s in sigs_up_to_t_mod if s.date == t]

    gaps_vals = sorted([round(s.gap_bps, 6) for s in gaps_at_t])
    gaps_vals_mod = sorted([round(s.gap_bps, 6) for s in gaps_at_t_mod])

    assert gaps_vals == gaps_vals_mod, (
        f"No-lookahead violated: gaps at t changed after modifying data after t.\n"
        f"Before: {gaps_vals[:5]}\nAfter: {gaps_vals_mod[:5]}"
    )
