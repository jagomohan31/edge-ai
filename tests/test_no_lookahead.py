"""test_no_lookahead.py: no-lookahead property using the new normalize/signals API."""
import numpy as np
import pandas as pd

from edge_ai.config import load_config
from edge_ai.normalize import build_gaps, normalize_panel
from edge_ai.signals import build_signals, find_alerts
from edge_ai.synthetic import make_synthetic_panel


def test_no_lookahead():
    cfg = load_config()
    panel = make_synthetic_panel(start="2025-01-02", end="2025-06-30", cfg=cfg, mode="noise_only", seed=3)
    pn = normalize_panel(panel, cfg)
    sessions = np.sort(pn["date"].unique())
    if len(sessions) < 4:
        return
    t = sessions[len(sessions) // 2]
    dev_end = pd.Timestamp(sessions[int(0.6 * len(sessions)) - 1])
    pn_t = pn[pn["date"] <= t].copy()
    gaps_t = build_gaps(pn_t, cfg)
    if gaps_t.empty:
        return
    g_t = find_alerts(build_signals(gaps_t, pn_t, cfg, dev_end), cfg)
    vals = sorted(g_t[g_t["date"] == t]["gap_bps"].round(6).tolist())
    # modifying data after t in the truncated panel has no effect (no rows after t)
    # Instead verify: rebuilding on full panel then slicing == slicing first
    gaps_full = build_gaps(pn, cfg)
    if gaps_full.empty:
        return
    g_full = find_alerts(build_signals(gaps_full, pn, cfg, dev_end), cfg)
    vals_full = sorted(g_full[g_full["date"] == t]["gap_bps"].round(6).tolist())
    assert vals == vals_full, (
        f"Lookahead: gaps at t differ between truncated and full panel.\\n"
        f"Truncated: {vals[:5]}\\nFull: {vals_full[:5]}"
    )
