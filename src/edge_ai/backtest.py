"""backtest.py: chronological backtest engine (Req 6).

Reference implementations: simulate_trade, make_px, legs_for, run_backtest
from edge_ai_pipeline.py / edge_ai_ref.py.

Key correctness properties:
- Signal at close of day t -> fill at NEXT session open (adverse slippage).
- Exit decided at close of t -> fill at NEXT session open (or current close * 3x if no volume).
- Every leg priced at its own contract's price.  No continuous series.
- Rejects fills when volume = 0 or lots > max_participation * volume.
- Forced exit before delivery_cutoff_sessions.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from edge_ai.config import Config
from edge_ai.signals import sessions_to_expiry

# ------------------------------------------------------------------ cost helpers (thin wrappers)

def _fill_price(open_px: float, side: str, symbol: str, cfg: Config, stress: float = 1.0) -> float:
    """Adverse fill at the next session open.  Buys pay up, sells give up.

    Reference: edge_ai_ref.py::fill_price (exact logic).
    """
    tick = cfg.contracts[symbol].tick_inr
    slip = cfg.costs.slippage_ticks_per_side * stress * tick
    return open_px + slip if side == "buy" else open_px - slip


def _trade_cost_inr(
    symbol: str, side: str, price: float, lots: int, cfg: Config,
    brokerage: bool = True,
) -> float:
    """Statutory charges for one leg, one side.

    Reference: edge_ai_ref.py::trade_cost_inr adapted to Config.
    """
    c      = cfg.contracts[symbol]
    cc     = cfg.costs
    notional = price * (c.lot_g / c.quote_g) * lots
    brok   = cc.brokerage_per_order_inr if brokerage else 0.0
    ctt    = notional * cc.ctt_sell    if side == "sell" else 0.0
    exch   = notional * cc.exchange_txn
    stamp  = notional * cc.stamp_buy   if side == "buy"  else 0.0
    sebi   = notional * cc.sebi_per_crore_inr / 1e7
    gst    = cc.gst * (brok + exch + sebi)
    return brok + ctt + exch + stamp + sebi + gst


def _leg_pnl_inr(symbol: str, sign: int, lots: int, p0: float, p1: float, cfg: Config) -> float:
    """P&L for one leg (sign=+1 long, -1 short).  Reference: edge_ai_ref.py::leg_pnl_inr."""
    c = cfg.contracts[symbol]
    return sign * lots * (c.lot_g / c.quote_g) * (p1 - p0)


def _fine_gram_exposure(legs: list[dict], cfg: Config) -> float:
    """Net fine-gram exposure.  Reference: edge_ai_ref.py::fine_gram_exposure."""
    return sum(
        L["sign"] * L["lots"] * cfg.contracts[L["symbol"]].lot_g * cfg.contracts[L["symbol"]].fineness
        for L in legs
    )


# ------------------------------------------------------------------ book helpers

def make_px(pn: pd.DataFrame) -> dict:
    """Index panel by (symbol, expiry) -> DataFrame[open, close, volume] by date.

    Reference: edge_ai_pipeline.py::make_px (exact copy adapted for column names).
    """
    return {
        k: d.set_index("date")[["open", "close", "volume"]].sort_index()
        for k, d in pn.groupby(["symbol", "expiry"])
    }


def legs_for(row, basket_g: int, cfg: Config, mult: int = 1) -> list[dict]:
    """Construct leg list for a signal row.

    Gap above baseline means A is expensive relative to B: short A, long B.
    Reference: edge_ai_pipeline.py::legs_for adapted to Config.
    """
    lots = {s: basket_g // cfg.contracts[s].lot_g for s in cfg.data.symbols}
    sign_a = -1 if row["dev"] > 0 else +1
    return [
        dict(symbol=row["fam_a"], expiry=row["expiry_a"], sign=sign_a,    lots=lots[row["fam_a"]] * mult),
        dict(symbol=row["fam_b"], expiry=row["expiry_b"], sign=-sign_a,   lots=lots[row["fam_b"]] * mult),
    ]


# ------------------------------------------------------------------ core simulator

def simulate_trade(
    px: dict,
    legs: list[dict],
    signal_date,
    z_by_date: pd.Series,
    sessions,
    cfg: Config,
    stress: float = 1.0,
):
    """Simulate one basket trade from signal to exit.

    Fill rule: signal at close of signal_date -> entry at NEXT session open (adverse slippage).
    Exit decided at close -> fills at NEXT session open (or at this close * 3x slippage if no volume).
    Returns None when the entry cannot be filled.

    Reference: edge_ai_ref.py::simulate_trade (exact logic, uses Config instead of cfg dict).
    """
    p      = cfg.signals
    lc     = cfg.lifecycle
    sess   = pd.to_datetime(sessions)
    idx    = {d: i for i, d in enumerate(sess)}
    i0     = idx.get(pd.Timestamp(signal_date))
    if i0 is None or i0 + 1 >= len(sess):
        return None

    def book(L):
        return px.get((L["symbol"], L["expiry"]))

    t_in = sess[i0 + 1]

    # Check entry fills (volume, participation)
    entry = {}
    for k, L in enumerate(legs):
        d = book(L)
        if d is None or t_in not in d.index:
            return None
        vol = d.loc[t_in, "volume"]
        if vol <= 0 or L["lots"] > cfg.liquidity.max_participation * vol:
            return None
        side = "buy" if L["sign"] > 0 else "sell"
        entry[k] = _fill_price(d.loc[t_in, "open"], side, L["symbol"], cfg, stress)

    cost = sum(
        _trade_cost_inr(L["symbol"], "buy" if L["sign"] > 0 else "sell", entry[k], L["lots"], cfg)
        for k, L in enumerate(legs)
    )
    prev = dict(entry)
    daily, held, k_i = [], 0, i0 + 1

    while True:
        t = sess[k_i]
        pnl = 0.0
        for k, L in enumerate(legs):
            d = book(L)
            c = d.loc[t, "close"] if (d is not None and t in d.index) else prev[k]
            pnl += _leg_pnl_inr(L["symbol"], L["sign"], L["lots"], prev[k], c, cfg)
            prev[k] = c
        held += 1
        z    = z_by_date.get(t, np.nan)
        left = min(sessions_to_expiry(sess, t, L["expiry"]) for L in legs)

        reason = None
        if np.isfinite(z) and abs(z) <= p.exit_z:
            reason = "reverted"
        elif np.isfinite(z) and abs(z) >= p.stop_z:
            reason = "stop"
        elif held >= p.holding_horizon_sessions:
            reason = "horizon"
        elif left <= lc.delivery_cutoff_sessions:
            reason = "delivery_cutoff"
        elif k_i + 1 >= len(sess):
            reason = "end_of_data"

        if reason is None:
            daily.append((t, pnl))
            k_i += 1
            continue

        # Exit fills
        t_out = sess[k_i + 1] if k_i + 1 < len(sess) else t
        ok    = (k_i + 1 < len(sess) and
                 all(t_out in book(L).index and book(L).loc[t_out, "volume"] > 0
                     for L in legs if book(L) is not None))
        exit_px = {}
        for k, L in enumerate(legs):
            side   = "sell" if L["sign"] > 0 else "buy"
            d      = book(L)
            base   = d.loc[t_out, "open"] if ok and d is not None and t_out in d.index else prev[k]
            exit_px[k] = _fill_price(base, side, L["symbol"], cfg, stress * (1 if ok else 3))
            pnl += _leg_pnl_inr(L["symbol"], L["sign"], L["lots"], prev[k], exit_px[k], cfg)
        cost += sum(
            _trade_cost_inr(L["symbol"], "sell" if L["sign"] > 0 else "buy", exit_px[k], L["lots"], cfg)
            for k, L in enumerate(legs)
        )
        t_end = t_out if ok else t
        daily.append((t_end, pnl))
        gross = float(sum(p_ for _, p_ in daily))
        return dict(
            signal_date=pd.Timestamp(signal_date), entry_date=t_in, exit_date=t_end,
            reason=reason, hold_sessions=held, gross_inr=gross, cost_inr=float(cost),
            net_inr=gross - float(cost), daily=daily,
            exposure_g=_fine_gram_exposure(legs, cfg),
        )


# ------------------------------------------------------------------ run_backtest

def run_backtest(
    g: pd.DataFrame,
    px: dict,
    pn: pd.DataFrame,
    cfg: Config,
    start,
    stress: float = 1.0,
) -> pd.DataFrame:
    """Chronological backtest: one open trade per series, at most max_open at once.

    Reference: edge_ai_pipeline.py::run_backtest adapted to Config.
    """
    sessions = np.sort(pn["date"].unique())
    z_series = {
        sid: d.set_index("date")["z"]
        for sid, d in g.groupby("series_id")
    }
    trades, open_until = [], {}
    for row in g[(g["alert"]) & (g["date"] > start)].itertuples(index=False):
        open_now = sum(1 for e in open_until.values() if e >= row.date)
        if (open_until.get(row.series_id, pd.Timestamp.min) >= row.date
                or open_now >= cfg.backtest.max_open):
            continue
        legs = legs_for(row._asdict(), cfg.backtest.basket_g, cfg)
        t = simulate_trade(px, legs, row.date, z_series[row.series_id], sessions, cfg, stress)
        if t is None:
            continue
        t.update(
            series_id=row.series_id, pair=row.pair, legs=legs,
            z_entry=row.z, gap_entry=row.gap_bps,
        )
        trades.append(t)
        open_until[row.series_id] = t["exit_date"]
    return pd.DataFrame(trades)


# ------------------------------------------------------------------ locked-window guard

def split_sessions(sessions, cfg: Config):
    """Return (develop_end, validate_end) timestamps."""
    n         = len(sessions)
    n_dev     = int(n * cfg.backtest.split.develop)
    n_val     = int(n * cfg.backtest.split.validate_)
    dev_end   = pd.Timestamp(sessions[n_dev - 1])
    val_end   = pd.Timestamp(sessions[n_dev + n_val - 1])
    return dev_end, val_end


def run_window(
    g: pd.DataFrame,
    px: dict,
    pn: pd.DataFrame,
    cfg: Config,
    window: str = "develop",
    locked_lock_path: str = "runs/locked.lock",
    force: bool = False,
    stress: float = 1.0,
) -> pd.DataFrame:
    """Run backtest for a named window (develop | validate | locked).

    Locked window guard: refuses a second run unless force=True.
    """
    import pathlib
    sessions  = np.sort(pn["date"].unique())
    dev_end, val_end = split_sessions(sessions, cfg)

    if window == "develop":
        start = pd.Timestamp(sessions[0]) - pd.Timedelta(days=1)
        end   = dev_end
    elif window == "validate":
        start = dev_end
        end   = val_end
    elif window == "locked":
        lock_path = pathlib.Path(locked_lock_path)
        if lock_path.exists() and not force:
            raise RuntimeError(
                "Locked window has already been run. "
                "Delete runs/locked.lock or pass --force to override."
            )
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text("locked")
        start = val_end
        end   = pd.Timestamp(sessions[-1])
    else:
        raise ValueError(f"Unknown window: {window!r}")

    g_win = g[(g["date"] > start) & (g["date"] <= end)].copy()
    return run_backtest(g_win, px, pn, cfg, start, stress)
