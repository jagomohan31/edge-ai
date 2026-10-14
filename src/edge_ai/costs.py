"""costs.py: full cost model per trade leg (Req 6.3).

Statutory costs for a two-leg round trip come to about 3.4 bps of one leg's notional.
Charges: CTT (sell side), exchange txn (both sides), stamp (buy side),
SEBI fee, GST on brokerage+exchange+SEBI, brokerage per order, slippage in ticks.
"""
from __future__ import annotations

from edge_ai.config import Config


def cost_per_leg(
    price: float,
    lots: int,
    symbol: str,
    side: str,  # 'buy' or 'sell'
    cfg: Config,
    slippage_multiplier: float = 1.0,
) -> dict[str, float]:
    """Compute all-in cost for one leg of a trade.

    Returns a dict with individual cost components and 'total_inr'.
    """
    c = cfg.contracts[symbol]
    cc = cfg.costs
    notional = price * c.lot_g / c.quote_g * lots

    brokerage = cc.brokerage_per_order_inr
    ctt = notional * cc.ctt_sell if side == "sell" else 0.0
    exchange = notional * cc.exchange_txn
    stamp = notional * cc.stamp_buy if side == "buy" else 0.0
    sebi = notional * cc.sebi_per_crore_inr / 1e7
    gst = cc.gst * (brokerage + exchange + sebi)
    slippage = cc.slippage_ticks_per_side * slippage_multiplier * c.tick_inr * c.lot_g / c.quote_g * lots

    total = brokerage + ctt + exchange + stamp + sebi + gst + slippage
    return {
        "brokerage": brokerage,
        "ctt": ctt,
        "exchange": exchange,
        "stamp": stamp,
        "sebi": sebi,
        "gst": gst,
        "slippage": slippage,
        "total_inr": total,
        "notional": notional,
        "total_bps": total / notional * 1e4 if notional > 0 else 0.0,
    }


def round_trip_cost_bps(
    price_a: float, lots_a: int, symbol_a: str,
    price_b: float, lots_b: int, symbol_b: str,
    cfg: Config,
    slippage_multiplier: float = 1.0,
) -> float:
    """Compute total round-trip cost in bps on leg-A notional.

    A two-leg round trip = 4 trades: buy A, sell B (open), sell A, buy B (close).
    """
    open_buy_a = cost_per_leg(price_a, lots_a, symbol_a, "buy", cfg, slippage_multiplier)
    open_sell_b = cost_per_leg(price_b, lots_b, symbol_b, "sell", cfg, slippage_multiplier)
    close_sell_a = cost_per_leg(price_a, lots_a, symbol_a, "sell", cfg, slippage_multiplier)
    close_buy_b = cost_per_leg(price_b, lots_b, symbol_b, "buy", cfg, slippage_multiplier)

    total_cost = (
        open_buy_a["total_inr"] + open_sell_b["total_inr"]
        + close_sell_a["total_inr"] + close_buy_b["total_inr"]
    )
    notional_a = open_buy_a["notional"]
    return total_cost / notional_a * 1e4 if notional_a > 0 else 0.0
