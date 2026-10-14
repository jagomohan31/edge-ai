"""dashboard.py: Streamlit multi-page dashboard for Edge AI (Req 7)."""
from __future__ import annotations

from pathlib import Path

import streamlit as st


# Detect synthetic data
def _is_synthetic() -> bool:
    panel_path = Path("data/clean/panel.parquet")
    if panel_path.exists():
        try:
            import pandas as pd
            df = pd.read_parquet(panel_path, columns=["synthetic"])
            return bool(df["synthetic"].any())
        except Exception:
            pass
    return True  # no data yet == demo mode


def main() -> None:
    st.set_page_config(
        page_title="Edge AI — MCX Gold Analytics",
        page_icon="🥇",
        layout="wide",
    )

    if _is_synthetic():
        st.error(
            "⚠️ **SYNTHETIC DATA** — All numbers on this dashboard are from the synthetic "
            "generator and do not represent real MCX prices. Fetch real data to remove this banner.",
            icon="🔴",
        )

    st.title("Edge AI — MCX Gold Futures Analytics")
    st.caption("Hack in Hills '26 · Problem Statement 03 · Commodity Derivatives Intelligence")

    pages = {
        "📊 Parity Monitor": _page_parity,
        "📈 Curve & Carry": _page_curve,
        "📅 Lifecycle Calendar": _page_lifecycle,
        "🚨 Alerts": _page_alerts,
        "🧪 Backtest Lab": _page_backtest,
        "🏥 Data Health": _page_health,
    }

    page = st.sidebar.radio("Page", list(pages.keys()))
    pages[page]()


def _load(path: str):
    import pandas as pd
    p = Path(path)
    if not p.exists():
        return None
    return pd.read_parquet(p)


def _page_parity() -> None:
    st.header("Parity Monitor")
    st.caption("Normalized price gaps between gold contract families (basis points)")
    gaps = _load("data/derived/gaps.parquet")
    if gaps is None or gaps.empty:
        st.info("No gaps data. Run `edge-ai analyze` first.")
        return
    latest = gaps[gaps["date"] == gaps["date"].max()].copy()
    st.metric("Latest date", str(latest["date"].iloc[0]))
    st.dataframe(
        latest[["fam_a", "fam_b", "dte_b", "gap_bps", "extrap_days", "liq_ok_a", "liq_ok_b", "stale"]],
        use_container_width=True,
    )
    import plotly.express as px
    fig = px.line(
        gaps.sort_values("date"),
        x="date", y="gap_bps",
        color="fam_a",
        facet_col="fam_b",
        title="Gap history (bps)",
    )
    st.plotly_chart(fig, use_container_width=True)


def _page_curve() -> None:
    st.header("Curve & Carry")
    curves = _load("data/derived/curves.parquet")
    factor = _load("data/derived/factor.parquet")
    if curves is None:
        st.info("No curve data. Run `edge-ai analyze` first.")
        return
    import plotly.express as px
    latest_date = curves["date"].max()
    latest_curves = curves[curves["date"] == latest_date]
    fig = px.line(
        latest_curves[latest_curves["traded"]],
        x="dte", y="ln_px_fine",
        color="family",
        title=f"Term structure — {latest_date}",
    )
    st.plotly_chart(fig, use_container_width=True)
    if factor is not None and not factor.empty:
        st.subheader("Gold Factor (G) history")
        st.line_chart(factor.set_index("date")["G"])
        st.subheader("Implied carry (annualized)")
        carry = curves[~curves["implied_carry_ann"].isna()]
        fig2 = px.line(carry, x="date", y="implied_carry_ann", color="family")
        st.plotly_chart(fig2, use_container_width=True)


def _page_lifecycle() -> None:
    st.header("Lifecycle Calendar")
    lc = _load("data/derived/lifecycle.parquet")
    if lc is None:
        st.info("No lifecycle data. Run `edge-ai build` first.")
        return
    st.dataframe(lc, use_container_width=True)


def _page_alerts() -> None:
    st.header("Alerts")
    st.caption("Quiet by default — every day produces a record. Silence means no gate passed.")
    gaps = _load("data/derived/gaps.parquet")
    panel = _load("data/clean/panel.parquet")
    if gaps is None or panel is None:
        st.info("Run `edge-ai analyze` first.")
        return
    from edge_ai.config import load_config
    from edge_ai.signals import compute_signals
    cfg = load_config()
    recs = compute_signals(gaps, panel, cfg)
    import pandas as pd
    df = pd.DataFrame([{
        "date": r.date, "pair": f"{r.fam_a}/{r.fam_b}",
        "expiry_b": r.expiry_b, "dte_b": r.dte_b,
        "gap_bps": round(r.gap_bps, 2),
        "z": round(r.z, 2) if r.z == r.z else None,
        "alert": r.alert,
        "gate_blocked": r.nearest_miss_gate,
        "net_edge_bps": round(r.net_edge_bps, 2) if r.net_edge_bps == r.net_edge_bps else None,
    } for r in recs])
    alerts = df[df["alert"]]
    no_signal = df[~df["alert"]]
    if alerts.empty:
        st.success("No alerts today — no gate fully passed.")
    else:
        st.subheader(f"🚨 {len(alerts)} Alert(s)")
        st.dataframe(alerts, use_container_width=True)
    with st.expander(f"No-signal records ({len(no_signal)})"):
        st.dataframe(no_signal[["date", "pair", "gate_blocked"]].tail(50), use_container_width=True)


def _page_backtest() -> None:
    st.header("Backtest Lab")
    import glob
    run_dirs = sorted(glob.glob("runs/*/summary.json"), reverse=True)
    if not run_dirs:
        st.info("No runs yet. Run `edge-ai backtest` first.")
        return
    import json
    run_options = []
    for path in run_dirs:
        with open(path) as f:
            s = json.load(f)
        run_options.append(s["run_id"])
    selected = st.selectbox("Run", run_options)
    run_dir = Path("runs") / selected
    equity = _load(str(run_dir / "equity.parquet"))
    trades = _load(str(run_dir / "trades.parquet"))
    if equity is not None:
        st.subheader("Net equity curve")
        st.line_chart(equity.set_index("date")["portfolio_value"])
    if trades is not None and not trades.empty:
        st.subheader(f"Trade blotter ({len(trades)} trades)")
        st.dataframe(trades, use_container_width=True)
        st.metric("Net P&L (₹)", f"{trades['net_pnl_inr'].sum():.2f}")
        st.metric("Mean P&L per trade (₹)", f"{trades['net_pnl_inr'].mean():.2f}")


def _page_health() -> None:
    st.header("Data Health")
    panel = _load("data/clean/panel.parquet")
    if panel is None:
        st.info("No panel. Run `edge-ai build` first.")
        return
    from edge_ai.config import load_config
    from edge_ai.qa import format_qa_report, run_qa
    cfg = load_config()
    qa = run_qa(panel, cfg)
    st.text(format_qa_report(qa))
    col1, col2, col3 = st.columns(3)
    col1.metric("Total rows", len(panel))
    col2.metric("Stale rows", int(panel["stale"].sum()))
    col3.metric("Zero-vol rows", int(panel["zero_vol"].sum()))


if __name__ == "__main__":
    main()
