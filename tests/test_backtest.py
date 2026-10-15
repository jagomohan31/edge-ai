"""tests/test_backtest.py: golden tests for backtest.py.

Ported from reference/test_ref.py (simulate_trade, sessions_to_expiry, fill/volume tests).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from edge_ai.backtest import (
    _trade_cost_inr,
    sessions_to_expiry,
    simulate_trade,
)
from edge_ai.config import load_config

CFG = load_config()
TS = pd.Timestamp


def _toy(volume_a=5000, volume_b=1000, expiry_a="2027-03-31", expiry_b="2027-04-05"):
    sessions = pd.bdate_range("2026-11-02", periods=40)
    a_close  = np.full(40, 12000.0)
    a_close[6], a_close[7], a_close[8] = 11995, 11992, 11990
    a_open   = np.full(40, 12000.0)
    a_open[9:] = 11990
    px = {
        ("GOLDPETAL", TS(expiry_a)): pd.DataFrame(
            {"open": a_open, "close": a_close, "volume": volume_a}, index=sessions
        ),
        ("GOLDM", TS(expiry_b)): pd.DataFrame(
            {"open": 120000.0, "close": 120000.0, "volume": volume_b}, index=sessions
        ),
    }
    legs = [
        dict(symbol="GOLDPETAL", expiry=TS(expiry_a), sign=-1, lots=200),
        dict(symbol="GOLDM",     expiry=TS(expiry_b), sign=+1, lots=2),
    ]
    z = pd.Series(np.nan, index=sessions)
    z.iloc[5], z.iloc[6], z.iloc[7], z.iloc[8] = 3.0, 2.5, 1.5, 0.3
    return px, legs, z, sessions


def test_simulate_trade_fills_next_session_and_matches_hand_calculation():
    px, legs, z, sessions = _toy()
    t = simulate_trade(px, legs, sessions[5], z, sessions, CFG)
    assert t is not None
    assert t["entry_date"] == sessions[6]     # fills at session 6 (t+1)
    assert t["exit_date"]  == sessions[9]     # z reverted at session 8 -> exits session 9
    assert t["reason"]     == "reverted"
    assert t["hold_sessions"] == 3

    # Short 200 PETAL: sell at open[6]+1 tick=11999, buy back at open[9]-1 tick=11989
    # Wait -- open[6]=12000, so entry fill = 12000 - 1 = 11999 (sell, adverse)
    # open[9] = 11990, exit fill = 11990 + 1 = 11991 (buy back, adverse)
    # PETAL P&L: (11999 - 11991) * 200 * 1 = +1600
    # Long 2 GOLDM: buy at open[6]+1=120001, sell at open[9]-1=119999
    # GOLDM P&L: (119999 - 120001) * 2 * 10 = -40
    assert t["gross_inr"] == pytest.approx(1600.0 - 40.0)

    expected_cost = (
        _trade_cost_inr("GOLDPETAL", "sell", 11999, 200, CFG)
        + _trade_cost_inr("GOLDM",    "buy",  120001, 2, CFG)
        + _trade_cost_inr("GOLDPETAL", "buy",  11991, 200, CFG)
        + _trade_cost_inr("GOLDM",    "sell", 119999, 2, CFG)
    )
    assert t["cost_inr"] == pytest.approx(expected_cost)
    assert t["net_inr"]  == pytest.approx(t["gross_inr"] - expected_cost)
    assert sum(p for _, p in t["daily"]) == pytest.approx(t["gross_inr"])


def test_no_fill_without_volume_or_above_participation_cap():
    # participation cap: max_participation=0.10, lots=200 -> need volume >= 2000
    px, legs, z, sessions = _toy(volume_a=1000)    # 1000 * 0.10 = 100 < 200 lots
    assert simulate_trade(px, legs, sessions[5], z, sessions, CFG) is None


def test_no_fill_when_goldm_has_zero_volume():
    px, legs, z, sessions = _toy()
    # zero out GOLDM volume on fill day (session 6)
    key = ("GOLDM", TS("2027-04-05"))
    px[key].iloc[6, px[key].columns.get_loc("volume")] = 0
    assert simulate_trade(px, legs, sessions[5], z, sessions, CFG) is None


def test_forced_exit_before_delivery_cutoff():
    # PETAL expires 11 sessions after the signal -> forced exit inside cutoff
    px, legs, z, sessions = _toy(expiry_a="2026-11-17")
    z[:] = 3.0   # never reverts on its own
    t = simulate_trade(px, legs, sessions[5], z, sessions, CFG)
    assert t is not None
    assert t["reason"] == "delivery_cutoff"
    decided_idx = list(sessions).index(t["exit_date"]) - 1
    decided = sessions[decided_idx]
    assert sessions_to_expiry(sessions, decided, legs[0]["expiry"]) <= CFG.lifecycle.delivery_cutoff_sessions


def test_sessions_to_expiry():
    s = pd.bdate_range("2026-11-02", periods=10)
    assert sessions_to_expiry(s, s[0], s[3]) == 3
    assert sessions_to_expiry(s, s[3], s[3]) == 0
