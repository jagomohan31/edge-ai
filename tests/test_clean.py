import pandas as pd

from edge_ai.clean import clean
from edge_ai.config import load_config
from edge_ai.qa import run_qa


def _make_raw(symbol="GOLDM", date_str="03/04/2026", expiry_str="05APR2026",
              close=700.0, volume=100, oi=500):
    return pd.DataFrame([{
        "Symbol": symbol,
        "Date": date_str,
        "ExpiryDate": expiry_str,
        "Open": close - 1,
        "High": close + 2,
        "Low": close - 2,
        "Close": close,
        "Volume": volume,
        "OpenInterest": oi,
        "synthetic": True,
    }])


def test_clean_basic():
    cfg = load_config()
    raw = _make_raw()
    df, warnings = clean(raw, cfg)
    assert not df.empty
    assert "date" in df.columns
    assert "expiry" in df.columns


def test_date_format_march_4():
    # 03/04/2026 must be parsed as March 4 (MM/DD/YYYY), not April 3
    cfg = load_config()
    raw = _make_raw(date_str="03/04/2026", expiry_str="05APR2026")
    df, _ = clean(raw, cfg)
    assert not df.empty
    parsed = df["date"].iloc[0]
    assert parsed.month == 3  # MM/DD/YYYY => month=3


def test_symbol_whitespace_stripped():
    cfg = load_config()
    raw = _make_raw(symbol=" GOLDM")
    df, warnings = clean(raw, cfg)
    assert not df.empty
    assert df["symbol"].iloc[0] == "GOLDM"


def test_gold_variant_warning():
    cfg = load_config()
    raw = pd.concat([
        _make_raw(symbol="GOLDM"),
        _make_raw(symbol="GOLDKG"),
    ], ignore_index=True)
    df, warnings = clean(raw, cfg)
    assert any("GOLDKG" in w for w in warnings)
    assert "GOLDKG" not in df["symbol"].values


def test_duplicate_rejected():
    cfg = load_config()
    raw = pd.concat([_make_raw(), _make_raw()], ignore_index=True)
    df, warnings = clean(raw, cfg)
    assert len(df) == 1
    assert any("duplicate" in w.lower() for w in warnings)


def test_qa_passes_clean_data():
    cfg = load_config()
    raw = _make_raw()
    df, warnings = clean(raw, cfg)
    qa = run_qa(df, cfg, warnings)
    price_check = next(c for c in qa["checks"] if "close > 0" in c["name"])
    assert price_check["passed"]
