"""lifecycle.py: contract listing, liquidity build-up, delivery cutoff (Req 6, 7)."""
from __future__ import annotations

import pandas as pd

from edge_ai.config import Config


def compute_lifecycle(panel: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Compute per-contract lifecycle events.

    Returns DataFrame: symbol, expiry, first_seen, first_traded,
    oi_peak_date, last_traded, delivery_cutoff_date.
    """
    records: list[dict] = []
    cutoff_sessions = cfg.lifecycle.delivery_cutoff_sessions

    for (sym, exp), grp in panel.groupby(["symbol", "expiry"]):
        grp_s = grp.sort_values("date")
        first_seen = grp_s["date"].min()

        traded = grp_s[~grp_s["zero_vol"]]
        first_traded = traded["date"].min() if not traded.empty else None
        last_traded = traded["date"].max() if not traded.empty else None

        oi_peak_date = grp_s.loc[grp_s["oi_g"].idxmax(), "date"] if not grp_s.empty else None

        # Delivery cutoff: last_traded minus cutoff_sessions trading days
        if last_traded is not None:
            all_dates = sorted(panel["date"].unique())
            try:
                idx = all_dates.index(last_traded)
                cutoff_idx = max(0, idx - cutoff_sessions)
                delivery_cutoff_date = all_dates[cutoff_idx]
            except ValueError:
                delivery_cutoff_date = last_traded
        else:
            delivery_cutoff_date = None

        records.append({
            "symbol": sym,
            "expiry": exp,
            "first_seen": first_seen,
            "first_traded": first_traded,
            "oi_peak_date": oi_peak_date,
            "last_traded": last_traded,
            "delivery_cutoff_date": delivery_cutoff_date,
        })

    return pd.DataFrame(records)
