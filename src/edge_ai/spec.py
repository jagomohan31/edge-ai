"""spec.py: contract constants, notional per lot, gram-basket helper.

All logic derives from the Config object; no magic numbers here.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from edge_ai.config import Config, ContractConfig


@dataclass(frozen=True)
class BasketAllocation:
    """Whole-lot allocation for a target gram basket."""

    symbol: str
    lots: int
    grams: float
    residual_g: float  # grams not covered due to lot rounding


def notional_per_lot(symbol: str, price: float, cfg: Config) -> float:
    """Return notional value in INR for one lot at *price* (per quote_g grams).

    Formula: price * lot_g / quote_g
    """
    c: ContractConfig = cfg.contracts[symbol]
    return price * c.lot_g / c.quote_g


def px_per_fine_gram(symbol: str, close: float, cfg: Config) -> float:
    """Return price per fine gram: close / quote_g / fineness."""
    c: ContractConfig = cfg.contracts[symbol]
    return close / c.quote_g / c.fineness


def vol_to_grams(symbol: str, volume: float, cfg: Config) -> float:
    """Convert volume (lots or units depending on config) to grams.

    When volume_units == 'lots': grams = volume * lot_g.
    When volume_units == 'units': grams = volume (already in grams or base units; warn).
    """
    c: ContractConfig = cfg.contracts[symbol]
    if cfg.volume_units == "lots":
        return volume * c.lot_g
    # units: pass through; caller must verify
    return volume


def gram_basket(target_g: float, symbol: str, cfg: Config) -> BasketAllocation:
    """Compute the whole-lot allocation closest to *target_g* grams for *symbol*.

    Rounds down to the nearest whole lot.
    """
    c: ContractConfig = cfg.contracts[symbol]
    lots = math.floor(target_g / c.lot_g)
    lots = max(lots, 1)  # at least 1 lot
    grams = lots * c.lot_g
    return BasketAllocation(
        symbol=symbol,
        lots=lots,
        grams=grams,
        residual_g=target_g - grams,
    )


def minimum_basket(cfg: Config) -> dict[str, BasketAllocation]:
    """Compute the minimum whole-lot basket (200 g) across all configured symbols.

    Returns a mapping symbol -> BasketAllocation.
    The smallest basket that is whole lots in all four families is 200 g:
    GOLDM=2 lots, GOLDTEN=20 lots, GOLDGUINEA=25 lots, GOLDPETAL=200 lots.
    """
    target = cfg.backtest.basket_g * cfg.backtest.basket_multiples
    return {sym: gram_basket(target, sym, cfg) for sym in cfg.data.symbols}


def net_fine_gram_exposure(allocations: dict[str, BasketAllocation], cfg: Config) -> float:
    """Return net fine-gram exposure: sum(lots * lot_g * fineness) across all legs."""
    total = 0.0
    for sym, alloc in allocations.items():
        c = cfg.contracts[sym]
        total += alloc.lots * c.lot_g * c.fineness
    return total
