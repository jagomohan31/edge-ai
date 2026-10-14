from edge_ai.config import load_config
from edge_ai.spec import (
    gram_basket,
    minimum_basket,
    net_fine_gram_exposure,
    notional_per_lot,
    px_per_fine_gram,
)


def test_notional_per_lot_goldm():
    cfg = load_config()
    assert abs(notional_per_lot("GOLDM", 7000.0, cfg) - 70000.0) < 1e-6


def test_px_per_fine_gram_goldm():
    cfg = load_config()
    expected = 700.0 / 10.0 / 0.995
    assert abs(px_per_fine_gram("GOLDM", 700.0, cfg) - expected) < 1e-6


def test_gram_basket_goldm():
    cfg = load_config()
    alloc = gram_basket(200.0, "GOLDM", cfg)
    assert alloc.lots == 2
    assert alloc.grams == 200.0
    assert alloc.residual_g == 0.0


def test_minimum_basket_200g():
    cfg = load_config()
    basket = minimum_basket(cfg)
    assert basket["GOLDM"].lots == 2
    assert basket["GOLDTEN"].lots == 20
    assert basket["GOLDGUINEA"].lots == 25
    assert basket["GOLDPETAL"].lots == 200


def test_net_fine_gram_exposure():
    cfg = load_config()
    basket = minimum_basket(cfg)
    exposure = net_fine_gram_exposure(basket, cfg)
    assert exposure > 0
