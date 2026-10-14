from edge_ai.config import load_config
from edge_ai.costs import cost_per_leg, round_trip_cost_bps


def test_statutory_costs_approx_3_4_bps():
    cfg = load_config()
    result = cost_per_leg(7000.0, 2, "GOLDM", "sell", cfg, slippage_multiplier=0)
    notional = result["notional"]
    statutory = result["ctt"] + result["exchange"] + result["sebi"]
    statutory_bps = statutory / notional * 1e4
    assert 0.5 < statutory_bps < 10.0, f"Statutory bps out of range: {statutory_bps:.3f}"


def test_round_trip_cost_positive():
    cfg = load_config()
    cost = round_trip_cost_bps(7000.0, 2, "GOLDM", 700.0, 20, "GOLDTEN", cfg)
    assert cost > 0


def test_buy_has_stamp_not_ctt():
    cfg = load_config()
    result = cost_per_leg(7000.0, 1, "GOLDM", "buy", cfg)
    assert result["stamp"] > 0
    assert result["ctt"] == 0.0


def test_sell_has_ctt_not_stamp():
    cfg = load_config()
    result = cost_per_leg(7000.0, 1, "GOLDM", "sell", cfg)
    assert result["ctt"] > 0
    assert result["stamp"] == 0.0
