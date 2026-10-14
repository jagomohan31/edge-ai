"""backtest.py: chronological backtest engine (Req 6).

Fill rules: orders created at close of t fill on t+1.
Whole-lot baskets, calendar enforcement, participation cap.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

import numpy as np
import pandas as pd

from edge_ai.config import Config
from edge_ai.costs import cost_per_leg
from edge_ai.signals import SignalRecord
from edge_ai.spec import gram_basket


@dataclass
class Position:
    """One open two-leg position."""

    trade_id: str
    fam_a: str
    fam_b: str
    expiry_b: object
    lots_a: int
    lots_b: int
    entry_date: object
    fill_date: object
    entry_px_a: float
    entry_px_b: float
    entry_cost_inr: float
    entry_signal: SignalRecord


@dataclass
class TradeRecord:
    """Completed round-trip trade."""

    trade_id: str
    entry_date: object
    exit_date: object
    fam_a: str
    fam_b: str
    expiry_b: object
    lots_a: int
    lots_b: int
    entry_px_a: float
    entry_px_b: float
    exit_px_a: float
    exit_px_b: float
    entry_cost_inr: float
    exit_cost_inr: float
    gross_pnl_inr: float
    net_pnl_inr: float
    exit_reason: str
    synthetic: bool


def _get_px(panel: pd.DataFrame, date_val: object, symbol: str, expiry: object | None) -> float | None:
    if expiry is not None:
        row = panel[(panel["date"] == date_val) & (panel["symbol"] == symbol) & (panel["expiry"] == expiry)]
    else:
        cands = panel[(panel["date"] == date_val) & (panel["symbol"] == symbol)]
        if "dte" in cands.columns:
            cands = cands[cands["dte"] > 0].sort_values("dte")
        row = cands
    if row.empty:
        return None
    return float(row["close"].iloc[0])


def _get_vol_g(panel: pd.DataFrame, date_val: object, symbol: str, expiry: object | None) -> float:
    if expiry is not None:
        row = panel[(panel["date"] == date_val) & (panel["symbol"] == symbol) & (panel["expiry"] == expiry)]
    else:
        cands = panel[(panel["date"] == date_val) & (panel["symbol"] == symbol)]
        if "dte" in cands.columns:
            cands = cands[cands["dte"] > 0].sort_values("dte")
        row = cands
    if row.empty:
        return 0.0
    return float(row["vol_g"].iloc[0])


def _split_sessions(sessions: list, cfg: Config) -> tuple[list, list, list]:
    """Split session list into develop, validate, locked windows."""
    n = len(sessions)
    n_dev = int(n * cfg.backtest.split.develop)
    n_val = int(n * cfg.backtest.split.validate_)
    develop = sessions[:n_dev]
    validate = sessions[n_dev: n_dev + n_val]
    locked = sessions[n_dev + n_val:]
    return develop, validate, locked


def run_backtest(
    panel: pd.DataFrame,
    signals: list[SignalRecord],
    cfg: Config,
    window: str = "develop",  # "develop" | "validate" | "locked"
    locked_lock_path: str = "runs/locked.lock",
    force: bool = False,
) -> tuple[list[TradeRecord], pd.DataFrame]:
    """Run the chronological backtest engine.

    Returns (trade_records, equity_df).
    equity_df has columns: date, portfolio_value, daily_pnl.
    """
    import pathlib

    sessions = sorted(panel["date"].unique())
    develop_s, validate_s, locked_s = _split_sessions(sessions, cfg)
    window_map = {"develop": develop_s, "validate": validate_s, "locked": locked_s}
    active_sessions = window_map[window]

    # Locked window guard
    if window == "locked":
        lock_path = pathlib.Path(locked_lock_path)
        if lock_path.exists() and not force:
            raise RuntimeError(
                "Locked window has already been run. "
                "Pass force=True or --force to override."
            )
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text("locked")

    signal_map: dict[object, list[SignalRecord]] = {}
    for sig in signals:
        if sig.alert:
            signal_map.setdefault(sig.date, []).append(sig)

    open_positions: list[Position] = []
    pending_entries: list[tuple[Position, object]] = []  # (position, fill_date)
    pending_exits: list[tuple[Position, object, str]] = []  # (position, fill_date, reason)
    trades: list[TradeRecord] = []
    equity_rows: list[dict] = []
    portfolio_value = 0.0

    for t_idx, t in enumerate(active_sessions):
        # Fill pending entries (decided at t-1, fill at t)
        new_entries: list[Position] = []
        for pos, fill_date in list(pending_entries):
            if fill_date != t:
                continue
            pending_entries.remove((pos, fill_date))
            # Check liquidity / participation at t
            px_a = _get_px(panel, t, pos.fam_a, None)
            px_b = _get_px(panel, t, pos.fam_b, pos.expiry_b)
            if px_a is None or px_b is None:
                continue  # can't fill

            # Participation cap
            vol_g_a = _get_vol_g(panel, t, pos.fam_a, None)
            max_g = vol_g_a * cfg.liquidity.max_participation
            cfg_contract = cfg.contracts[pos.fam_a]
            max_lots = int(max_g / cfg_contract.lot_g) if cfg_contract.lot_g > 0 else pos.lots_a
            if max_lots == 0:
                continue

            actual_lots_a = min(pos.lots_a, max_lots)
            pos.lots_a = actual_lots_a

            cost_a = cost_per_leg(px_a, pos.lots_a, pos.fam_a, "buy", cfg)
            cost_b = cost_per_leg(px_b, pos.lots_b, pos.fam_b, "sell", cfg)
            pos.entry_px_a = px_a
            pos.entry_px_b = px_b
            pos.entry_cost_inr = cost_a["total_inr"] + cost_b["total_inr"]
            pos.fill_date = t
            new_entries.append(pos)

        open_positions.extend(new_entries)

        # Fill pending exits
        for pos, fill_date, reason in list(pending_exits):
            if fill_date != t:
                continue
            pending_exits.remove((pos, fill_date, reason))
            if pos not in open_positions:
                continue
            px_a = _get_px(panel, t, pos.fam_a, None)
            px_b = _get_px(panel, t, pos.fam_b, pos.expiry_b)
            if px_a is None or px_b is None:
                continue

            # P&L on actual held contracts
            cost_a_exit = cost_per_leg(px_a, pos.lots_a, pos.fam_a, "sell", cfg)
            cost_b_exit = cost_per_leg(px_b, pos.lots_b, pos.fam_b, "buy", cfg)
            exit_cost = cost_a_exit["total_inr"] + cost_b_exit["total_inr"]

            cfg_a = cfg.contracts[pos.fam_a]
            cfg_b = cfg.contracts[pos.fam_b]
            gross_pnl = (
                (px_a - pos.entry_px_a) * pos.lots_a * cfg_a.lot_g / cfg_a.quote_g
                - (px_b - pos.entry_px_b) * pos.lots_b * cfg_b.lot_g / cfg_b.quote_g
            )
            net_pnl = gross_pnl - pos.entry_cost_inr - exit_cost
            portfolio_value += net_pnl

            is_synthetic = bool(panel[panel["date"] == t]["synthetic"].any()) if "synthetic" in panel.columns else False

            trades.append(TradeRecord(
                trade_id=pos.trade_id,
                entry_date=pos.entry_date,
                exit_date=t,
                fam_a=pos.fam_a,
                fam_b=pos.fam_b,
                expiry_b=pos.expiry_b,
                lots_a=pos.lots_a,
                lots_b=pos.lots_b,
                entry_px_a=pos.entry_px_a,
                entry_px_b=pos.entry_px_b,
                exit_px_a=px_a,
                exit_px_b=px_b,
                entry_cost_inr=pos.entry_cost_inr,
                exit_cost_inr=exit_cost,
                gross_pnl_inr=gross_pnl,
                net_pnl_inr=net_pnl,
                exit_reason=reason,
                synthetic=is_synthetic,
            ))
            open_positions.remove(pos)

        # Decide exits for open positions (signal-based and horizon)
        for pos in list(open_positions):
            sessions_held = active_sessions.index(t) - active_sessions.index(pos.fill_date) if pos.fill_date in active_sessions else 0
            exit_reason = None
            if sessions_held >= cfg.signals.holding_horizon_sessions:
                exit_reason = "horizon"
            # stop_z: check current gap z
            # (simplified: use gap from today's signal if available)
            if exit_reason is None:
                today_sigs = signal_map.get(t, [])
                for sig in today_sigs:
                    if sig.fam_a == pos.fam_a and sig.fam_b == pos.fam_b and sig.expiry_b == pos.expiry_b:
                        if not np.isnan(sig.z) and abs(sig.z) >= cfg.signals.stop_z:
                            exit_reason = "stop_z"
                        break
            if exit_reason:
                next_t_idx = t_idx + 1
                if next_t_idx < len(active_sessions):
                    fill_t = active_sessions[next_t_idx]
                    pending_exits.append((pos, fill_t, exit_reason))

        # Decide entries from today's alerts (fill on t+1)
        if t_idx + 1 < len(active_sessions):
            next_t = active_sessions[t_idx + 1]
            for sig in signal_map.get(t, []):
                alloc_a = gram_basket(cfg.backtest.basket_g, sig.fam_a, cfg)
                alloc_b = gram_basket(cfg.backtest.basket_g, sig.fam_b, cfg)
                pos = Position(
                    trade_id=str(uuid.uuid4())[:8],
                    fam_a=sig.fam_a,
                    fam_b=sig.fam_b,
                    expiry_b=sig.expiry_b,
                    lots_a=alloc_a.lots,
                    lots_b=alloc_b.lots,
                    entry_date=t,
                    fill_date=next_t,
                    entry_px_a=0.0,
                    entry_px_b=0.0,
                    entry_cost_inr=0.0,
                    entry_signal=sig,
                )
                pending_entries.append((pos, next_t))

        equity_rows.append({"date": t, "portfolio_value": portfolio_value, "daily_pnl": 0.0})

    equity_df = pd.DataFrame(equity_rows)
    if not equity_df.empty:
        equity_df["daily_pnl"] = equity_df["portfolio_value"].diff().fillna(0.0)

    return trades, equity_df
