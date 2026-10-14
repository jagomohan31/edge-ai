"""Configuration loader: reads configs/default.yaml and validates with pydantic."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator


class ContractConfig(BaseModel):
    lot_g: float
    quote_g: float
    fineness: float
    tick_inr: float
    expiry_window: tuple[int, int]


class DataConfig(BaseModel):
    raw_dir: str = "data/raw"
    clean_dir: str = "data/clean"
    derived_dir: str = "data/derived"
    throttle_seconds: float = 1.0
    symbols: list[str] = Field(default_factory=lambda: ["GOLDM", "GOLDTEN", "GOLDGUINEA", "GOLDPETAL"])
    reference_symbols: list[str] = Field(default_factory=list)


class CurveConfig(BaseModel):
    max_extrapolation_days: int = 7
    gold_factor_horizon_days: int = 30


class SignalsConfig(BaseModel):
    baseline_window: int = 60
    dte_buckets: list[int] = Field(default_factory=lambda: [0, 5, 10, 20, 40, 400])
    z_threshold: float = 2.0
    min_net_edge_bps: float = 2.0
    cooldown_sessions: int = 5
    max_maturity_gap_days: int = 7
    holding_horizon_sessions: int = 5
    stop_z: float = 4.0


class LiquidityConfig(BaseModel):
    min_traded_g_quantile: float = 0.25
    min_oi_g_quantile: float = 0.25
    max_participation: float = 0.10


class LifecycleConfig(BaseModel):
    delivery_cutoff_sessions: int = 5


class CostsConfig(BaseModel):
    ctt_sell: float = 0.0001
    exchange_txn: float = 0.000021
    stamp_buy: float = 0.00002
    sebi_per_crore_inr: float = 10.0
    gst: float = 0.18
    brokerage_per_order_inr: float = 20.0
    slippage_ticks_per_side: int = 1
    slippage_stress: list[int] = Field(default_factory=lambda: [1, 2, 3])


class SplitConfig(BaseModel):
    develop: float = 0.6
    validate_: float = Field(0.2, alias="validate")
    locked: float = 0.2

    @model_validator(mode="after")
    def check_sum(self) -> SplitConfig:
        total = self.develop + self.validate_ + self.locked
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"split fractions must sum to 1.0, got {total}")
        return self


class BacktestConfig(BaseModel):
    fill_rule: Literal["next_open", "next_close", "worst_open_close"] = "next_open"
    split: SplitConfig = Field(default_factory=SplitConfig)
    basket_g: float = 200.0
    basket_multiples: int = 1


class StatsConfig(BaseModel):
    bootstrap_resamples: int = 10000
    placebo_draws: int = 1000
    seed: int = 42


class Config(BaseModel):
    data: DataConfig = Field(default_factory=DataConfig)
    volume_units: Literal["lots", "units"] = "lots"
    contracts: dict[str, ContractConfig] = Field(default_factory=dict)
    curve: CurveConfig = Field(default_factory=CurveConfig)
    signals: SignalsConfig = Field(default_factory=SignalsConfig)
    liquidity: LiquidityConfig = Field(default_factory=LiquidityConfig)
    lifecycle: LifecycleConfig = Field(default_factory=LifecycleConfig)
    costs: CostsConfig = Field(default_factory=CostsConfig)
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)
    stats: StatsConfig = Field(default_factory=StatsConfig)


_DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "configs" / "default.yaml"


def load_config(path: Path | None = None) -> Config:
    """Load and validate the YAML configuration file."""
    cfg_path = Path(path) if path else _DEFAULT_CONFIG_PATH
    with cfg_path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return Config.model_validate(raw)
