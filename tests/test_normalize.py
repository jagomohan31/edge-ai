"""tests/test_normalize.py: golden tests for normalize.py.

Tests ported from reference/test_ref.py (test_parity_identity_*, test_deck_worked_example_*,
test_ln_price_at_*, test_parity_none_*).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from edge_ai.config import load_config
from edge_ai.normalize import build_gaps, ln_price_at, normalize_panel, parity_row

CFG = load_config()
TS = pd.Timestamp


def _day_panel(rows):
    """Helper: build a minimal normalized panel from (date, symbol, expiry, close, volume) rows."""
    df = pd.DataFrame(rows, columns=["date", "symbol", "expiry", "close", "volume"])
    df["open"] = df["close"]
    df["high"] = df["close"]
    df["low"] = df["close"]
    df["oi"] = df["volume"]
    df["date"]   = pd.to_datetime(df["date"])
    df["expiry"] = pd.to_datetime(df["expiry"])
    return normalize_panel(df, CFG)


def _fine(S, c, dte):
    """Price per fine gram from one underlying at spot S with carry c and dte days."""
    return S * np.exp(c * dte / 365)


# ---------- ln_price_at ----------

def test_ln_price_at_interpolates_extrapolates_and_limits():
    cv = pd.DataFrame({"dte": [20, 50], "px_g_fine": [100.0, 110.0]})
    assert ln_price_at(cv, 35) == pytest.approx(np.interp(35, [20, 50], np.log([100, 110])))
    # extrapolation at short end
    assert ln_price_at(cv, 17) == pytest.approx(
        np.log(100) + (np.log(110) - np.log(100)) / 30 * (17 - 20)
    )
    # too far: NaN
    assert np.isnan(ln_price_at(cv, 5, max_gap=7))
    # only one point: NaN
    assert np.isnan(ln_price_at(cv.iloc[:1], 20))


# ---------- parity identity ----------

def test_parity_identity_and_zero_residual_when_one_underlying():
    S, c, d0 = 12000.0, 0.07, TS("2026-11-09")
    e_b = TS("2026-12-04")
    e1  = TS("2026-11-30")
    e2  = TS("2026-12-31")

    def _px(sym, expiry):
        c_ = CFG.contracts[sym]
        fine = _fine(S, c, (expiry - d0).days)
        return fine * c_.fineness * c_.quote_g

    day = _day_panel([
        (d0, "GOLDM",    e_b, _px("GOLDM",    e_b), 1000),
        (d0, "GOLDPETAL", e1, _px("GOLDPETAL", e1), 5000),
        (d0, "GOLDPETAL", e2, _px("GOLDPETAL", e2), 5000),
    ])

    r = parity_row(day, "GOLDPETAL", "GOLDM", e_b)
    assert r is not None
    # exact identity
    assert r["naive_bps"] == pytest.approx(r["purity_bps"] + r["maturity_bps"] + r["gap_bps"], abs=1e-9)
    # purity term: ln(0.999 / 0.995)
    assert r["purity_bps"] == pytest.approx(1e4 * np.log(0.999 / 0.995), abs=1e-9)
    # no residual when same underlying
    assert abs(r["gap_bps"]) < 1e-6


def test_deck_worked_example_83_40_52_minus9():
    """Documented worked example: 83 bps naive, ~40 purity, ~52 maturity, ~-9 residual."""
    d0  = TS("2026-11-09")
    e_b = TS("2026-12-04")    # GOLDM expires 4 Dec (25 days)
    e1  = TS("2026-12-31")    # PETAL near expiry
    e2  = TS("2027-01-31")    # PETAL far expiry

    p1 = 12100.0 / 0.999                         # PETAL 31 Dec fine price from a Rs 12,100/g quote
    p2 = p1 * np.exp(0.07 * 31 / 365)            # next expiry on 7% carry

    day = _day_panel([
        (d0, "GOLDM",    e_b, 120000.0,          1000),
        (d0, "GOLDPETAL", e1, 12100.0,            5000),
        (d0, "GOLDPETAL", e2, 0.999 * p2,         5000),
    ])
    r = parity_row(day, "GOLDPETAL", "GOLDM", e_b, max_leg_gap_days=30, max_extrap_days=30)
    assert r is not None
    assert r["naive_bps"]    == pytest.approx(83.0, abs=0.1)
    assert r["purity_bps"]   == pytest.approx(40.1, abs=0.1)
    assert r["maturity_bps"] == pytest.approx(51.8, abs=0.1)
    assert r["gap_bps"]      == pytest.approx(-8.9, abs=0.1)


def test_parity_none_when_family_has_one_expiry_or_leg_too_far():
    d0  = TS("2026-11-09")
    day = _day_panel([
        (d0, "GOLDM",    TS("2026-12-04"), 120000.0, 10),
        (d0, "GOLDPETAL", TS("2026-11-30"), 12000.0,  10),
    ])
    # Only one PETAL expiry -> cannot interpolate -> None
    assert parity_row(day, "GOLDPETAL", "GOLDM", TS("2026-12-04")) is None


# ---------- build_gaps coverage ----------

def test_build_gaps_returns_dataframe_with_required_columns():
    d0  = TS("2026-11-09")
    e_b = TS("2026-12-04")
    e1  = TS("2026-11-30")
    e2  = TS("2026-12-31")
    day = _day_panel([
        (d0, "GOLDM",    e_b, 120000.0, 1000),
        (d0, "GOLDPETAL", e1,  12000.0, 5000),
        (d0, "GOLDPETAL", e2,  12100.0, 5000),
    ])
    gaps = build_gaps(day, CFG)
    assert not gaps.empty
    for col in ("date", "fam_a", "fam_b", "gap_bps", "purity_bps", "maturity_bps", "naive_bps"):
        assert col in gaps.columns, f"missing column: {col}"
    # identity holds for every row
    for _, row in gaps.iterrows():
        assert row["naive_bps"] == pytest.approx(
            row["purity_bps"] + row["maturity_bps"] + row["gap_bps"], abs=1e-9
        )
