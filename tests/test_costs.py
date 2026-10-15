"""tests/test_costs.py: golden tests for costs.py.

Ported from reference/test_ref.py (test_statutory_costs_*, test_ctt_only_*, test_fill_price_*).
"""
from __future__ import annotations

import pytest

from edge_ai.backtest import _fill_price, _trade_cost_inr
from edge_ai.config import load_config

CFG = load_config()


def test_statutory_costs_about_3_4_bps_for_two_leg_round_trip():
    """Reference golden test: round-trip statutory costs ~3.44 bps (no brokerage)."""
    from copy import deepcopy
    cfg0 = deepcopy(CFG)
    cfg0.costs.brokerage_per_order_inr = 0.0

    pB, pA = 120000.0, 12000.0   # 2 GOLDM lots, 200 PETAL lots: equal notional

    total = (
        _trade_cost_inr("GOLDM",    "buy",  pB, 2,   cfg0)
        + _trade_cost_inr("GOLDPETAL", "sell", pA, 200, cfg0)
        + _trade_cost_inr("GOLDM",    "sell", pB, 2,   cfg0)
        + _trade_cost_inr("GOLDPETAL", "buy",  pA, 200, cfg0)
    )
    # GOLDM units_per_lot = 100/10 = 10; 2 lots = 20 units * 120000 = 2,400,000
    notional_leg = pB * (100 / 10) * 2
    assert notional_leg == pytest.approx(pA * 200)   # equal notional
    assert 1e4 * total / notional_leg == pytest.approx(3.44, abs=0.02)


def test_ctt_only_on_sell_and_stamp_only_on_buy():
    from copy import deepcopy
    cfg0 = deepcopy(CFG)
    cfg0.costs.brokerage_per_order_inr = 0.0
    cfg0.costs.exchange_txn = 0.0
    cfg0.costs.sebi_per_crore_inr = 0.0

    n = 12000.0 * 200   # notional for 200 PETAL lots at 12000
    assert _trade_cost_inr("GOLDPETAL", "sell", 12000.0, 200, cfg0) == pytest.approx(n * 1e-4)
    assert _trade_cost_inr("GOLDPETAL", "buy",  12000.0, 200, cfg0) == pytest.approx(n * 2e-5)


def test_fill_price_is_adverse():
    # GOLDM tick = 1.  slip=1 tick per side.
    assert _fill_price(100.0, "buy",  "GOLDM", CFG)         == pytest.approx(101.0)
    assert _fill_price(100.0, "sell", "GOLDM", CFG)         == pytest.approx(99.0)
    assert _fill_price(100.0, "buy",  "GOLDM", CFG, stress=3) == pytest.approx(103.0)
