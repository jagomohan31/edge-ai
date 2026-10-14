from edge_ai.config import load_config


def test_load_default_config():
    cfg = load_config()
    assert cfg.volume_units in ("lots", "units")
    assert "GOLDM" in cfg.contracts
    assert cfg.contracts["GOLDM"].lot_g == 100
    assert cfg.contracts["GOLDM"].fineness == 0.995


def test_contract_constants():
    cfg = load_config()
    assert cfg.contracts["GOLDTEN"].lot_g == 10
    assert cfg.contracts["GOLDTEN"].fineness == 0.999
    assert cfg.contracts["GOLDGUINEA"].lot_g == 8
    assert cfg.contracts["GOLDPETAL"].lot_g == 1


def test_split_sums_to_one():
    cfg = load_config()
    s = cfg.backtest.split
    assert abs(s.develop + s.validate_ + s.locked - 1.0) < 1e-9
