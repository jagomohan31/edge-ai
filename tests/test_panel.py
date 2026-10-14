import tempfile
from datetime import date

from edge_ai.config import load_config
from edge_ai.panel import build_panel
from edge_ai.synthetic import generate_and_save


def test_panel_has_dte_and_session_idx():
    cfg = load_config()
    with tempfile.TemporaryDirectory() as tmp:
        cfg.data.raw_dir = tmp + "/raw"
        cfg.data.clean_dir = tmp + "/clean"
        generate_and_save(date(2025, 1, 2), date(2025, 3, 31), cfg, raw_dir=cfg.data.raw_dir)
        panel = build_panel(cfg, save=True)
        assert "dte" in panel.columns
        assert "session_idx" in panel.columns
        assert panel["session_idx"].nunique() > 1


def test_panel_session_idx_monotone():
    cfg = load_config()
    with tempfile.TemporaryDirectory() as tmp:
        cfg.data.raw_dir = tmp + "/raw"
        cfg.data.clean_dir = tmp + "/clean"
        generate_and_save(date(2025, 1, 2), date(2025, 3, 31), cfg, raw_dir=cfg.data.raw_dir)
        panel = build_panel(cfg, save=True)
        date_idx = panel.drop_duplicates("date").sort_values("date")["session_idx"].values
        assert list(date_idx) == list(range(len(date_idx)))
