from datetime import date

from edge_ai.config import load_config
from edge_ai.synthetic import generate_bhavcopy


def test_generates_rows():
    cfg = load_config()
    df = generate_bhavcopy(date(2025, 1, 2), date(2025, 1, 31), cfg)
    assert not df.empty
    assert "Symbol" in df.columns


def test_all_rows_synthetic():
    cfg = load_config()
    df = generate_bhavcopy(date(2025, 1, 2), date(2025, 1, 10), cfg)
    assert df["synthetic"].all()


def test_anomalies_injected():
    cfg = load_config()
    df = generate_bhavcopy(date(2025, 1, 2), date(2025, 3, 31), cfg, inject_anomalies=True)
    has_padded = df["Symbol"].str.startswith(" ").any()
    assert has_padded, "Expected at least one space-padded symbol anomaly"


def test_symbols_present():
    cfg = load_config()
    df = generate_bhavcopy(date(2025, 1, 2), date(2025, 2, 28), cfg)
    syms = df["Symbol"].str.strip().unique()
    for s in cfg.data.symbols:
        assert s in syms, f"{s} not in generated data"
