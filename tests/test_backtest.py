from datetime import date

import pandas as pd
import pytest

from edge_ai.backtest import _split_sessions, run_backtest
from edge_ai.clean import clean
from edge_ai.config import load_config
from edge_ai.synthetic import generate_bhavcopy


def _make_panel(cfg, start=date(2025, 1, 2), end=date(2025, 6, 30)):
    raw_df = generate_bhavcopy(start, end, cfg, inject_anomalies=False)
    df, _ = clean(raw_df, cfg)
    if df.empty:
        return df
    df["dte"] = (pd.to_datetime(df["expiry"]) - pd.to_datetime(df["date"])).dt.days
    sessions = sorted(df["date"].unique())
    df["session_idx"] = df["date"].map({d: i for i, d in enumerate(sessions)})
    return df


def test_split_sessions_proportions():
    cfg = load_config()
    sessions = list(range(100))
    dev, val, locked = _split_sessions(sessions, cfg)
    assert len(dev) == 60
    assert len(val) == 20
    assert len(locked) == 20


def test_no_trade_outside_calendar():
    cfg = load_config()
    panel = _make_panel(cfg)
    if panel.empty:
        return
    trades, equity = run_backtest(panel, [], cfg, window="develop")
    dates = set(panel["date"].unique())
    for t in trades:
        assert t.fill_date in dates, f"Trade filled outside panel: {t.fill_date}"


def test_equity_df_has_required_cols():
    cfg = load_config()
    panel = _make_panel(cfg)
    if panel.empty:
        return
    _, equity = run_backtest(panel, [], cfg, window="develop")
    assert "date" in equity.columns
    assert "portfolio_value" in equity.columns
    assert "daily_pnl" in equity.columns


def test_locked_guard(tmp_path):
    cfg = load_config()
    panel = _make_panel(cfg)
    if panel.empty:
        return
    lock_path = str(tmp_path / "locked.lock")
    run_backtest(panel, [], cfg, window="locked", locked_lock_path=lock_path)
    with pytest.raises(RuntimeError, match="Locked window"):
        run_backtest(panel, [], cfg, window="locked", locked_lock_path=lock_path, force=False)
