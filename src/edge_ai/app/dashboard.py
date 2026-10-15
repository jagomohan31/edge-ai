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
        page_icon="gold",
        layout="wide",
    )

    if _is_synthetic():
        st.error(
            "SYNTHETIC DATA — All numbers on this dashboard are from the synthetic "
            "generator and do not represent real MCX prices. Fetch real data to remove this banner.",
            icon="red_circle",
        )

    st.title("Edge AI — MCX Gold Futures Analytics")
    st.caption("Hack in Hills '26  |  Problem Statement 03  |  Commodity Derivatives Intelligence")

    pages = {
        "Parity Monitor": _page_parity,
        "Curve & Carry": _page_curve,
        "Lifecycle Calendar": _page_lifecycle,
        "Alerts": _page_alerts,
        "Backtest Lab": _page_backtest,
        "Data Health": _page_health,
    }

    page = st.sidebar.radio("Page", list(pages.keys()))
    pages[page]()


def _load(path: str):
    import pandas as pd
    p = Path(path)
    if not p.exists():
        return None
    return pd.read_parquet(p)

def _net_col(trades):
    """Return the net P&L column name regardless of which schema the run used."""
    if 'net_inr' in trades.columns:
        return 'net_inr'
    if 'net_pnl_inr' in trades.columns:
        return 'net_pnl_inr'
    return None


def _gross_col(trades):
    """Return the gross P&L column name."""
    if 'gross_inr' in trades.columns:
        return 'gross_inr'
    if 'gross_pnl_inr' in trades.columns:
        return 'gross_pnl_inr'
    return None


def _cost_col(trades):
    """Return the cost column name."""
    if 'cost_inr' in trades.columns:
        return 'cost_inr'
    if 'entry_cost_inr' in trades.columns:
        # old schema: entry_cost + exit_cost
        return None  # handled specially
    return None



def _page_parity() -> None:
    st.header("Parity Monitor")
    st.caption("Normalized price gaps between gold contract families (basis points)")
    gaps = _load("data/derived/gaps.parquet")
    if gaps is None or gaps.empty:
        st.info("No gaps data. Run `edge-ai analyze` first.")
        return

    import plotly.express as px

    latest_date = gaps["date"].max()
    latest = gaps[gaps["date"] == latest_date].copy()

    st.metric("Latest date", str(latest_date))

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Latest gaps")
        st.dataframe(
            latest[["fam_a", "fam_b", "dte_b", "gap_bps", "extrap_days", "liq_ok_a", "liq_ok_b", "stale"]],
            use_container_width=True,
        )
    with col2:
        st.subheader("Purity / carry / noise decomposition")
        st.caption("Gap components are not yet decomposed in this build. Shown: raw gap with cost band.")
        if not latest.empty:
            fig_bar = px.bar(
                latest.sort_values("gap_bps"),
                x="gap_bps", y="fam_a",
                orientation="h",
                color="gap_bps",
                color_continuous_scale="RdYlGn_r",
                title="Current gap (bps) by family pair",
                labels={"fam_a": "Family A", "gap_bps": "Gap (bps)"},
            )
            st.plotly_chart(fig_bar, use_container_width=True)

    st.subheader("Gap history")
    fig = px.line(
        gaps.sort_values("date"),
        x="date", y="gap_bps",
        color="fam_a",
        facet_col="fam_b",
        title="Parity gap history (bps) — past-only baseline",
        labels={"gap_bps": "Gap (bps)", "date": "Date"},
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

    col1, col2 = st.columns(2)
    with col1:
        st.subheader(f"Term structure — {latest_date}")
        fig = px.line(
            latest_curves[latest_curves["traded"]],
            x="dte", y="ln_px_fine",
            color="family",
            markers=True,
            title="ln(price per fine gram) vs days-to-expiry",
            labels={"dte": "Days to expiry", "ln_px_fine": "ln(px per fine gram)"},
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        if factor is not None and not factor.empty:
            st.subheader("Constant-maturity gold factor G")
            st.line_chart(factor.set_index("date")["G"])

    if "implied_carry_ann" in curves.columns:
        carry = curves[curves["implied_carry_ann"].notna()]
        if not carry.empty:
            st.subheader("Implied annualised carry by family")
            fig2 = px.line(
                carry, x="date", y="implied_carry_ann",
                color="family",
                title="Implied carry (annualised) history",
                labels={"implied_carry_ann": "Carry (ann.)", "date": "Date"},
            )
            st.plotly_chart(fig2, use_container_width=True)


def _page_lifecycle() -> None:
    st.header("Lifecycle Calendar")
    lc = _load("data/derived/lifecycle.parquet")
    if lc is None:
        st.info("No lifecycle data. Run `edge-ai build` first.")
        return

    st.subheader("Contract calendar")
    st.dataframe(lc, use_container_width=True)

    import pandas as pd
    import plotly.express as px

    lc2 = lc.copy()
    for col in ["first_seen", "first_traded", "last_traded", "delivery_cutoff_date"]:
        if col in lc2.columns:
            lc2[col] = pd.to_datetime(lc2[col], errors="coerce")

    if "first_traded" in lc2.columns and "last_traded" in lc2.columns:
        gantt_rows = []
        for _, row in lc2.iterrows():
            if pd.notna(row.get("first_traded")) and pd.notna(row.get("last_traded")):
                gantt_rows.append({
                    "Contract": f"{row['symbol']} {row['expiry']}",
                    "Start": row["first_traded"],
                    "Finish": row["last_traded"],
                    "Symbol": row["symbol"],
                })
        if gantt_rows:
            gantt_df = pd.DataFrame(gantt_rows)
            fig = px.timeline(
                gantt_df, x_start="Start", x_end="Finish",
                y="Contract", color="Symbol",
                title="Contract trading windows",
            )
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(fig, use_container_width=True)


def _page_alerts() -> None:
    st.header("Alerts")
    st.caption("Quiet by default — every day produces a record. Silence means no gate passed.")

    gaps = _load("data/derived/gaps.parquet")
    panel = _load("data/clean/panel.parquet")
    if gaps is None or panel is None:
        st.info("Run `edge-ai analyze` first.")
        return

    import pandas as pd
    import plotly.express as px

    from edge_ai.config import load_config
    from edge_ai.signals import compute_signals

    cfg = load_config()
    recs = compute_signals(gaps, panel, cfg)

    df = pd.DataFrame([{
        "date": r.date,
        "pair": f"{r.fam_a}/{r.fam_b}",
        "expiry_b": r.expiry_b,
        "dte_b": r.dte_b,
        "gap_bps": round(r.gap_bps, 2),
        "z": round(r.z, 2) if r.z == r.z else None,
        "alert": r.alert,
        "gate_blocked": r.nearest_miss_gate,
        "net_edge_bps": round(r.net_edge_bps, 2) if r.net_edge_bps == r.net_edge_bps else None,
    } for r in recs])

    alerts = df[df["alert"]]
    no_signal = df[~df["alert"]]

    col1, col2, col3 = st.columns(3)
    col1.metric("Total signal records", len(df))
    col2.metric("Alerts fired", len(alerts))
    col3.metric("No-signal records", len(no_signal))

    if not alerts.empty:
        st.subheader(f"Alerts ({len(alerts)})")
        st.dataframe(alerts, use_container_width=True)

        fig = px.scatter(
            alerts, x="date", y="gap_bps",
            color="pair", size="z",
            title="Alerts: gap (bps) and z-score over time",
            labels={"gap_bps": "Gap (bps)", "date": "Date"},
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.success("No alerts fired on this dataset. Silence is a valid, honest result.")

    with st.expander(f"No-signal records — nearest miss ({len(no_signal)})"):
        st.dataframe(
            no_signal[["date", "pair", "gate_blocked", "gap_bps", "z"]].tail(100),
            use_container_width=True,
        )


def _page_backtest() -> None:
    st.header("Backtest Lab")

    import glob
    import json

    run_dirs = sorted(glob.glob("runs/*/summary.json"), reverse=True)
    if not run_dirs:
        st.info("No runs yet. Run `edge-ai backtest` first.")
        return

    run_options = []
    for path in run_dirs:
        with open(path) as f:
            s = json.load(f)
        run_options.append((s["run_id"], s.get("window", "?"), s.get("n_trades", 0)))

    labels = [f"{r} ({w}, {n} trades)" for r, w, n in run_options]
    selected_idx = st.selectbox("Run", range(len(labels)), format_func=lambda i: labels[i])
    run_id, window, _ = run_options[selected_idx]
    run_dir = Path("runs") / run_id

    import plotly.express as px
    import plotly.graph_objects as go

    equity = _load(str(run_dir / "equity.parquet"))
    trades = _load(str(run_dir / "trades.parquet"))

    if equity is not None and not equity.empty:
        st.subheader("Net equity curve")
        fig_eq = px.line(
            equity, x="date", y="portfolio_value",
            title=f"Net portfolio value — {window} window",
            labels={"portfolio_value": "Portfolio value (INR)", "date": "Date"},
        )
        st.plotly_chart(fig_eq, use_container_width=True)

    if trades is not None and not trades.empty:
        gc = _gross_col(trades)
        gross = float(trades[gc].sum()) if gc else (float((trades['gross_pnl_inr']).sum()) if 'gross_pnl_inr' in trades.columns else 0.0)
        cc = _cost_col(trades)
        if cc:
            costs = float(trades[cc].sum())
        elif 'entry_cost_inr' in trades.columns and 'exit_cost_inr' in trades.columns:
            costs = float((trades['entry_cost_inr'] + trades['exit_cost_inr']).sum())
        else:
            costs = 0.0
        nc = _net_col(trades)
        net = float(trades[nc].sum()) if nc else gross - costs

        # Attribution waterfall
        st.subheader("P&L attribution waterfall")
        waterfall_fig = go.Figure(go.Waterfall(
            name="P&L",
            orientation="v",
            measure=["relative", "relative", "total"],
            x=["Gross spread P&L", "Costs", "Net P&L"],
            y=[gross, -costs, 0],
            connector={"line": {"color": "rgb(63, 63, 63)"}},
            decreasing={"marker": {"color": "#EF553B"}},
            increasing={"marker": {"color": "#00CC96"}},
            totals={"marker": {"color": "#636EFA"}},
        ))
        waterfall_fig.update_layout(title="Gross → Costs → Net P&L (INR)")
        st.plotly_chart(waterfall_fig, use_container_width=True)

        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Gross P&L (INR)", f"₹{gross:,.0f}")
        col2.metric("Total costs (INR)", f"₹{costs:,.0f}", delta=f"-₹{costs:,.0f}", delta_color="inverse")
        col3.metric("Net P&L (INR)", f"₹{net:,.0f}")
        col4.metric("Trades", len(trades))

        # Bootstrap CI
        from edge_ai.config import load_config
        from edge_ai.stats import bootstrap_mean_pnl, slippage_stress, sub_period_results
        cfg = load_config()
        bs = bootstrap_mean_pnl(trades, cfg)
        st.subheader("Bootstrap confidence interval (mean net P&L per trade)")
        bc1, bc2, bc3 = st.columns(3)
        bc1.metric("Mean (INR)", f"₹{bs['mean']:,.0f}" if bs["mean"] == bs["mean"] else "n/a")
        bc2.metric("95% CI low", f"₹{bs['ci_low']:,.0f}" if bs["ci_low"] == bs["ci_low"] else "n/a")
        bc3.metric("95% CI high", f"₹{bs['ci_high']:,.0f}" if bs["ci_high"] == bs["ci_high"] else "n/a")

        # Slippage stress
        st.subheader("Slippage sensitivity")
        sl_df = slippage_stress(trades, cfg.costs.slippage_stress)
        if not sl_df.empty:
            fig_sl = px.bar(
                sl_df, x="slippage_multiplier", y="net_pnl",
                title="Net P&L vs slippage cost multiplier",
                labels={"slippage_multiplier": "Slippage multiplier", "net_pnl": "Net P&L (INR)"},
                color="net_pnl",
                color_continuous_scale=["red", "green"],
            )
            st.plotly_chart(fig_sl, use_container_width=True)

        # Sub-period breakdown
        st.subheader("Sub-period (quarterly) breakdown")
        sp = sub_period_results(trades)
        if not sp.empty:
            sp.columns = ["Quarter", "Net P&L", "Mean P&L", "Trades"]
            st.dataframe(sp, use_container_width=True)

        # Trade blotter
        with st.expander(f"Trade blotter ({len(trades)} trades)"):
            st.dataframe(trades, use_container_width=True)


def _page_health() -> None:
    st.header("Data Health")
    panel = _load("data/clean/panel.parquet")
    if panel is None:
        st.info("No panel. Run `edge-ai build` first.")
        return

    import plotly.express as px

    from edge_ai.config import load_config
    from edge_ai.qa import format_qa_report, run_qa

    cfg = load_config()
    qa = run_qa(panel, cfg)
    st.text(format_qa_report(qa))

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total rows", len(panel))
    col2.metric("Stale rows", int(panel["stale"].sum()))
    col3.metric("Zero-vol rows", int(panel["zero_vol"].sum()))
    col4.metric("Synthetic rows", int(panel["synthetic"].sum()) if "synthetic" in panel.columns else 0)

    st.subheader("Volume (grams) by symbol over time")
    if "vol_g" in panel.columns and "date" in panel.columns:
        fig = px.line(
            panel[panel["vol_g"] > 0].groupby(["date", "symbol"])["vol_g"].sum().reset_index(),
            x="date", y="vol_g", color="symbol",
            title="Daily traded volume (grams) per symbol",
            labels={"vol_g": "Volume (grams)", "date": "Date"},
        )
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Open interest (grams) by symbol over time")
    if "oi_g" in panel.columns and "date" in panel.columns:
        fig2 = px.line(
            panel.groupby(["date", "symbol"])["oi_g"].sum().reset_index(),
            x="date", y="oi_g", color="symbol",
            title="Daily open interest (grams) per symbol",
            labels={"oi_g": "Open interest (grams)", "date": "Date"},
        )
        st.plotly_chart(fig2, use_container_width=True)


if __name__ == "__main__":
    main()
