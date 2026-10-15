"""dashboard.py: Streamlit multi-page dashboard for Edge AI (Req 7)."""
from __future__ import annotations

import glob
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

_CSS = """
<style>
[data-testid="stSidebar"] {
    background: linear-gradient(180deg,#0f0f1a 0%,#1a1a2e 60%,#16213e 100%);
}
[data-testid="stSidebar"] button {
    color: #c5cae9 !important;
    background: transparent;
    border: none;
    text-align: left;
    font-size: 14px;
}
[data-testid="stSidebar"] button:hover {
    color: #ffffff !important;
    background: rgba(99,110,250,0.12) !important;
}
.main .block-container { padding-top:1.2rem; max-width:1200px; }
[data-testid="metric-container"] {
    background:#1e1e2e; border:1px solid #2a2a3e;
    border-radius:10px; padding:10px 16px !important;
}
[data-testid="stMetricValue"] { color:#ffffff !important; font-size:20px !important; }
[data-testid="stMetricLabel"] { color:#9fa8da !important; }
.synth { background:#2d1515; border:1px solid #c44; border-radius:8px;
    padding:10px 16px; margin-bottom:12px; color:#f8b4b4; font-size:13px; }
.live-badge { background:#1a3a1a; border:1px solid #2a8a2a; border-radius:8px;
    padding:10px 16px; margin-bottom:12px; color:#a8f0a8; font-size:13px; }
</style>
"""

def _is_synthetic() -> bool:
    p = Path("data/clean/panel.parquet")
    if p.exists():
        try:
            import pandas as pd
            return bool(pd.read_parquet(p, columns=["synthetic"])["synthetic"].any())
        except Exception:
            pass
    return True


def _latest_date() -> str:
    p = Path("data/clean/panel.parquet")
    if p.exists():
        try:
            import pandas as pd
            d = pd.read_parquet(p, columns=["date"])["date"].max()
            return str(d)[:10]
        except Exception:
            pass
    return "no data"


def _load(path: str):
    import pandas as pd
    p = Path(path)
    return pd.read_parquet(p) if p.exists() else None


def _nc(t):
    return next((c for c in ("net_inr", "net_pnl_inr") if c in t.columns), None)


def _gc(t):
    return next((c for c in ("gross_inr", "gross_pnl_inr") if c in t.columns), None)


def _cc_sum(t) -> float:
    if "cost_inr" in t.columns:
        return float(t["cost_inr"].sum())
    if "entry_cost_inr" in t.columns:
        return float((t["entry_cost_inr"] + t["exit_cost_inr"]).sum())
    return 0.0


def _inr(v) -> str:
    try:
        return "n/a" if v != v else f"\u20b9{v:,.0f}"
    except Exception:
        return "n/a"


def _run_cmd(args: list[str]) -> tuple[int, str, str]:
    """Run edge-ai CLI command, return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "edge_ai"] + args,
            capture_output=True, text=True, timeout=120,
            cwd=str(Path(__file__).parent.parent.parent.parent),
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as exc:
        return 1, "", str(exc)


PAGES = [
    ("\U0001f4ca", "Parity Monitor"),
    ("\U0001f4c8", "Curve & Carry"),
    ("\U0001f4c5", "Lifecycle"),
    ("\U0001f6a8", "Alerts"),
    ("\U0001f9ea", "Backtest Lab"),
    ("\U0001f3e5", "Data Health"),
]

def _sidebar() -> str:
    with st.sidebar:
        st.markdown(
            "<div style='padding:16px 0 8px;font-size:22px;font-weight:700;"
            "color:#636efa;'>\U0001f947 Edge AI</div>"
            "<div style='font-size:11px;color:#505070;padding-bottom:10px;"
            "border-bottom:1px solid #252535;margin-bottom:10px;'>"
            "MCX Gold Futures Analytics</div>",
            unsafe_allow_html=True,
        )
        if "page" not in st.session_state:
            st.session_state["page"] = PAGES[0][1]
        for icon, label in PAGES:
            active = st.session_state["page"] == label
            bg = "rgba(99,110,250,0.18)" if active else "transparent"
            bl = "3px solid #636efa" if active else "3px solid transparent"
            st.markdown(
                f"<div style='background:{bg};border-left:{bl};"
                "border-radius:8px;margin:2px 0;'>",
                unsafe_allow_html=True,
            )
            if st.button(f"{icon}  {label}", key=f"nav_{label}",
                         use_container_width=True):
                st.session_state["page"] = label
            st.markdown("</div>", unsafe_allow_html=True)

        # --- Live data panel ---
        st.markdown(
            "<hr style='border-color:#252535;margin:16px 0 12px;'>"
            "<div style='font-size:11px;color:#636efa;font-weight:600;"
            "margin-bottom:8px;'>\U0001f4e1 LIVE DATA</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div style='font-size:11px;color:#707090;margin-bottom:8px;'>"
            f"Last data: <b style='color:#a0a0c0;'>{_latest_date()}</b></div>",
            unsafe_allow_html=True,
        )
        curl_exists = Path("docs/bhavcopy_request.curl").exists()
        curl_text = open("docs/bhavcopy_request.curl").read().strip() if curl_exists else ""
        has_curl = curl_exists and len(curl_text) > 50 and "curl" in curl_text.lower()

        if not has_curl:
            st.markdown(
                "<div style='font-size:11px;color:#f0a060;background:#2a1f10;"
                "border:1px solid #6a4020;border-radius:6px;padding:8px;margin-bottom:8px;'>"
                "\u26a0\ufe0f Paste MCX cURL into<br>"
                "<code>docs/bhavcopy_request.curl</code><br>"
                "to enable live fetch</div>",
                unsafe_allow_html=True,
            )
        else:
            if st.button("\U0001f504 Fetch Today & Rebuild", use_container_width=True,
                         key="fetch_today"):
                today = datetime.now().strftime("%Y-%m-%d")
                with st.spinner("Fetching MCX data..."):
                    rc, out, err = _run_cmd(["fetch", "--start", today, "--end", today])
                if rc == 0:
                    with st.spinner("Rebuilding pipeline..."):
                        _run_cmd(["build"])
                        _run_cmd(["analyze"])
                        _run_cmd(["signals"])
                    st.success("\u2705 Data updated!")
                    st.rerun()
                else:
                    st.error(f"Fetch failed:\n{err[:300]}")

            if st.button("\U0001f504 Full Rebuild (last 30 days)", use_container_width=True,
                         key="fetch_month"):
                import datetime as dt
                end = dt.date.today()
                start = end - dt.timedelta(days=30)
                with st.spinner(f"Fetching {start} \u2192 {end}..."):
                    rc, out, err = _run_cmd(["fetch", "--start", str(start), "--end", str(end)])
                if rc == 0:
                    with st.spinner("Building pipeline..."):
                        _run_cmd(["build"])
                        _run_cmd(["analyze"])
                        _run_cmd(["signals"])
                    st.success("\u2705 Pipeline updated!")
                    st.rerun()
                else:
                    st.error(f"Error: {err[:300]}")

        auto_refresh = st.checkbox(
            "\U0001f501 Auto-refresh (30 s)",
            value=False,
            key="auto_refresh",
            help="Reload dashboard data every 30 seconds",
        )
        if auto_refresh:
            import time
            time.sleep(30)
            st.rerun()

        st.markdown(
            "<hr style='border-color:#252535;margin:16px 0 8px;'>"
            "<div style='font-size:10px;color:#404055;text-align:center;'>"
            "Hack in Hills '26 \u00b7 PS-03 \u00b7 v1.2.0</div>",
            unsafe_allow_html=True,
        )
    return st.session_state["page"]

def _hdr(title: str, sub: str = "") -> None:
    st.markdown(
        f"<div style='border-bottom:1px solid #2a2a3a;padding-bottom:12px;"
        f"margin-bottom:16px;'><span style='font-size:24px;font-weight:700;'>"
        f"{title}</span>"
        + (f"<br><span style='font-size:13px;color:#808090;'>{sub}</span>" if sub else "")
        + "</div>",
        unsafe_allow_html=True,
    )


def _page_parity() -> None:
    _hdr("\U0001f4ca Parity Monitor",
         "Normalized price gaps between gold contract families (basis points)")
    gaps = _load("data/derived/gaps.parquet")
    if gaps is None or gaps.empty:
        st.info("No gaps data. Run `edge-ai analyze` first.")
        return
    import plotly.express as px
    latest_date = gaps["date"].max()
    latest = gaps[gaps["date"] == latest_date].copy()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Latest date", str(latest_date)[:10])
    c2.metric("Pair count", len(latest))
    c3.metric("Max gap (bps)", f"{latest['gap_bps'].abs().max():.1f}")
    liq = int((latest["liq_ok_a"] & latest["liq_ok_b"]).sum()) \
        if "liq_ok_a" in latest.columns else 0
    c4.metric("Liquid pairs", liq)
    col_a, col_b = st.columns([3, 2])
    with col_a:
        st.subheader("Latest gaps")
        disp = [c for c in ["fam_a", "fam_b", "dte_b", "gap_bps", "leg_gap_days",
                             "liq_ok_a", "liq_ok_b", "stale"] if c in latest.columns]
        st.dataframe(latest[disp], use_container_width=True, hide_index=True)
    with col_b:
        fig = px.bar(latest.sort_values("gap_bps"), x="gap_bps", y="fam_a",
                     orientation="h", color="gap_bps",
                     color_continuous_scale="RdYlGn_r", template="plotly_dark",
                     title="Gap by family (bps)", labels={"fam_a": "", "gap_bps": "bps"})
        fig.update_layout(margin=dict(l=0, r=0, t=36, b=0), height=260,
                          coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)
    st.subheader("Gap history")
    fig2 = px.line(gaps.sort_values("date"), x="date", y="gap_bps",
                   color="fam_a", facet_col="fam_b", template="plotly_dark",
                   title="Parity gap history (bps)", labels={"gap_bps": "bps", "date": ""})
    fig2.update_layout(margin=dict(t=40, b=0), height=320)
    st.plotly_chart(fig2, use_container_width=True)


def _page_curve() -> None:
    _hdr("\U0001f4c8 Curve & Carry",
         "Term structure, implied carry, constant-maturity gold factor G")
    curves = _load("data/derived/curves.parquet")
    factor = _load("data/derived/factor.parquet")
    if curves is None:
        st.info("No curve data. Run `edge-ai analyze` first.")
        return
    import plotly.express as px
    latest_date = curves["date"].max()
    lc = curves[curves["date"] == latest_date]
    col_a, col_b = st.columns(2)
    with col_a:
        fig = px.line(lc[lc["traded"]], x="dte", y="ln_px_fine", color="family",
                      markers=True, template="plotly_dark",
                      title=f"Term structure {str(latest_date)[:10]}",
                      labels={"dte": "Days to expiry", "ln_px_fine": "ln(price/fine g)"})
        fig.update_layout(margin=dict(t=40, b=0), height=320)
        st.plotly_chart(fig, use_container_width=True)
    with col_b:
        if factor is not None and not factor.empty:
            fig_g = px.line(factor, x="date", y="G", template="plotly_dark",
                            title="Gold factor G (INR/fine gram)",
                            labels={"G": "G (INR)", "date": ""})
            fig_g.update_layout(margin=dict(t=40, b=0), height=320)
            st.plotly_chart(fig_g, use_container_width=True)
    if "implied_carry_ann" in curves.columns:
        carry = curves[curves["implied_carry_ann"].notna()]
        if not carry.empty:
            fig_c = px.line(carry, x="date", y="implied_carry_ann", color="family",
                            template="plotly_dark", title="Implied annualised carry",
                            labels={"implied_carry_ann": "Carry (ann.)", "date": ""})
            fig_c.update_layout(margin=dict(t=40, b=0), height=300)
            st.plotly_chart(fig_c, use_container_width=True)

def _page_lifecycle() -> None:
    _hdr("\U0001f4c5 Lifecycle Calendar",
         "Contract listing, liquidity build-up, delivery cutoff")
    lc = _load("data/derived/lifecycle.parquet")
    if lc is None:
        st.info("No lifecycle data. Run `edge-ai build` first.")
        return
    import pandas as pd
    import plotly.express as px
    st.subheader("Contract summary")
    st.dataframe(lc, use_container_width=True, hide_index=True)
    lc2 = lc.copy()
    for col in ["first_traded", "last_traded"]:
        if col in lc2.columns:
            lc2[col] = pd.to_datetime(lc2[col], errors="coerce")
    if "first_traded" in lc2.columns and "last_traded" in lc2.columns:
        rows = [{"Contract": f"{r['symbol']} {str(r['expiry'])[:7]}",
                 "Start": r["first_traded"], "Finish": r["last_traded"],
                 "Symbol": r["symbol"]}
                for _, r in lc2.iterrows()
                if pd.notna(r.get("first_traded")) and pd.notna(r.get("last_traded"))]
        if rows:
            gdf = pd.DataFrame(rows)
            fig = px.timeline(gdf, x_start="Start", x_end="Finish",
                              y="Contract", color="Symbol", template="plotly_dark",
                              title="Contract active trading windows")
            fig.update_yaxes(autorange="reversed")
            fig.update_layout(margin=dict(t=40, b=0), height=500)
            st.plotly_chart(fig, use_container_width=True)


def _page_alerts() -> None:
    _hdr("\U0001f6a8 Alerts",
         "Quiet by default. Every day produces a record. Silence means no gate passed.")
    panel = _load("data/clean/panel.parquet")
    if panel is None:
        st.info("Run `edge-ai build` first.")
        return
    import plotly.express as px

    from edge_ai.config import load_config
    from edge_ai.signals import compute_signals
    cfg = load_config()
    sigs = compute_signals(panel, cfg)
    if not hasattr(sigs, "columns") or "alert" not in sigs.columns:
        st.warning("Signals format unexpected.")
        return
    alerts = sigs[sigs["alert"]]
    no_sig = sigs[~sigs["alert"]]
    c1, c2, c3 = st.columns(3)
    c1.metric("Total records", len(sigs))
    c2.metric("\U0001f6a8 Alerts fired", len(alerts))
    c3.metric("\U0001f910 No-signal records", len(no_sig))
    if not alerts.empty:
        st.subheader(f"Active alerts ({len(alerts)})")
        st.dataframe(alerts, use_container_width=True, hide_index=True)
        fig = px.scatter(alerts, x="date", y="gap_bps",
                         color="pair" if "pair" in alerts.columns else "fam_a",
                         size="z" if "z" in alerts.columns else None,
                         template="plotly_dark", title="Alert timeline")
        fig.update_layout(margin=dict(t=40, b=0), height=300)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.success(
            "\U0001f910 **No alerts fired.** No gap survived all gates after costs. "
            "This is a valid, honest result -- the system is working correctly."
        )
    if "blocked_by" in no_sig.columns:
        st.subheader("Gate blocking breakdown")
        blk = no_sig["blocked_by"].value_counts().reset_index()
        blk.columns = ["Gate", "Count"]
        fig_b = px.bar(blk, x="Count", y="Gate", orientation="h",
                       color="Count", color_continuous_scale="Blues",
                       template="plotly_dark", title="Why signals were blocked")
        fig_b.update_layout(margin=dict(t=40, b=0), height=260,
                             coloraxis_showscale=False)
        st.plotly_chart(fig_b, use_container_width=True)
    with st.expander(f"\U0001f4cb No-signal log ({len(no_sig)} records, last 200)"):
        show = [c for c in ["date", "pair", "fam_a", "fam_b", "blocked_by",
                             "gap_bps", "z", "net_edge_bps"] if c in no_sig.columns]
        st.dataframe(no_sig[show].tail(200), use_container_width=True, hide_index=True)


def _page_backtest() -> None:
    _hdr("\U0001f9ea Backtest Lab",
         "Equity curve, P&L waterfall, bootstrap CI, slippage stress, trade blotter")
    run_dirs = sorted(glob.glob("runs/*/summary.json"), reverse=True)
    if not run_dirs:
        st.info("No runs yet. Run `edge-ai backtest` first.")
        return
    import plotly.express as px
    import plotly.graph_objects as go
    run_opts = []
    for rp in run_dirs:
        with open(rp) as f:
            s = json.load(f)
        run_opts.append((s["run_id"], s.get("window", "?"), s.get("n_trades", 0)))
    labels = [f"{r}  --  {w} window  ({n} trades)" for r, w, n in run_opts]
    idx = st.selectbox("Select run", range(len(labels)), format_func=lambda i: labels[i])
    run_id, window, _ = run_opts[idx]
    run_dir = Path("runs") / run_id
    equity = _load(str(run_dir / "equity.parquet"))
    trades = _load(str(run_dir / "trades.parquet"))
    if trades is None or trades.empty:
        st.info("0 trades in this run -- no alert passed all gates after costs. "
                "Select an older run from the dropdown to see historical results.")
        return
    gc = _gc(trades)
    nc = _nc(trades)
    gross = float(trades[gc].sum()) if gc else 0.0
    costs = _cc_sum(trades)
    net = float(trades[nc].sum()) if nc else gross - costs
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Gross P&L", _inr(gross))
    c2.metric("Total costs", _inr(costs))
    delta_label = "positive" if net > 0 else "negative"
    delta_color = "normal" if net > 0 else "inverse"
    c3.metric("Net P&L", _inr(net), delta=delta_label, delta_color=delta_color)
    c4.metric("Trades", len(trades))
    t1, t2, t3, t4 = st.tabs(["Equity Curve", "Attribution Waterfall",
                               "Statistics", "Trade Blotter"])
    with t1:
        if equity is not None and not equity.empty:
            fig_eq = px.line(equity, x="date", y="portfolio_value",
                             template="plotly_dark",
                             title=f"Net equity curve -- {window} window",
                             labels={"portfolio_value": "Portfolio value (INR)", "date": ""})
            fig_eq.add_hline(y=1_000_000, line_dash="dot", line_color="#555",
                             annotation_text="Starting capital")
            fig_eq.update_layout(margin=dict(t=40, b=0), height=380)
            st.plotly_chart(fig_eq, use_container_width=True)
    with t2:
        wf = go.Figure(go.Waterfall(
            orientation="v", measure=["relative", "relative", "total"],
            x=["Gross spread P&L", "Costs", "Net P&L"],
            y=[gross, -costs, 0],
            connector={"line": {"color": "#444"}},
            decreasing={"marker": {"color": "#EF553B"}},
            increasing={"marker": {"color": "#00CC96"}},
            totals={"marker": {"color": "#636EFA"}},
            text=[_inr(gross), _inr(costs), _inr(net)],
            textposition="outside",
        ))
        wf.update_layout(title="P&L waterfall: Gross to Costs to Net",
                         template="plotly_dark", height=380, margin=dict(t=50, b=0))
        st.plotly_chart(wf, use_container_width=True)
    with t3:
        from edge_ai.config import load_config
        from edge_ai.stats import bootstrap_mean_pnl, slippage_stress, sub_period_results
        cfg = load_config()
        if nc:
            t_std = trades.rename(columns={nc: "net_inr"}) if nc != "net_inr" else trades.copy()
            if gc and gc != "gross_inr":
                t_std = t_std.rename(columns={gc: "gross_inr"})
            if "cost_inr" not in t_std.columns and "entry_cost_inr" in t_std.columns:
                t_std["cost_inr"] = t_std["entry_cost_inr"] + t_std["exit_cost_inr"]
            bs = bootstrap_mean_pnl(t_std, cfg)
            st.subheader("Bootstrap CI (mean net P&L per trade)")
            b1, b2, b3 = st.columns(3)
            b1.metric("Mean", _inr(bs["mean"]))
            b2.metric("95% CI low", _inr(bs["ci_low"]))
            b3.metric("95% CI high", _inr(bs["ci_high"]))
            sl = slippage_stress(t_std, cfg.costs.slippage_stress)
            if not sl.empty:
                st.subheader("Slippage stress test")
                fig_sl = px.bar(sl, x="slippage_multiplier", y="net_pnl",
                                color="net_pnl",
                                color_continuous_scale=["#EF553B", "#00CC96"],
                                template="plotly_dark",
                                title="Net P&L vs slippage multiplier",
                                labels={"slippage_multiplier": "Multiplier",
                                        "net_pnl": "Net P&L"})
                fig_sl.update_layout(margin=dict(t=40, b=0), height=280,
                                     coloraxis_showscale=False)
                st.plotly_chart(fig_sl, use_container_width=True)
        sp = sub_period_results(trades)
        if not sp.empty:
            st.subheader("Sub-period (quarterly) breakdown")
            sp.columns = ["Quarter", "Net P&L", "Mean P&L", "Trades"]
            st.dataframe(sp, use_container_width=True, hide_index=True)
    with t4:
        st.subheader(f"Trade blotter -- {len(trades)} trades")
        st.dataframe(trades, use_container_width=True, hide_index=True)

def _page_health() -> None:
    _hdr("\U0001f3e5 Data Health", "QA report, volume and open interest over time")
    panel = _load("data/clean/panel.parquet")
    if panel is None:
        st.info("No panel. Run `edge-ai build` first.")
        return
    import plotly.express as px

    from edge_ai.config import load_config
    from edge_ai.qa import format_qa_report, run_qa
    cfg = load_config()
    qa = run_qa(panel, cfg)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total rows", f"{len(panel):,}")
    c2.metric("Sessions", panel["date"].nunique())
    c3.metric("Stale rows", int(panel["stale"].sum()))
    c4.metric("Zero-vol rows", int(panel["zero_vol"].sum()))
    with st.expander("Full QA report"):
        st.code(format_qa_report(qa))
    col_a, col_b = st.columns(2)
    with col_a:
        if "vol_g" in panel.columns:
            vol = (panel[panel["vol_g"] > 0]
                   .groupby(["date", "symbol"])["vol_g"].sum().reset_index())
            fig = px.line(vol, x="date", y="vol_g", color="symbol",
                          template="plotly_dark", title="Daily volume (grams)",
                          labels={"vol_g": "Volume (g)", "date": ""})
            fig.update_layout(margin=dict(t=40, b=0), height=300)
            st.plotly_chart(fig, use_container_width=True)
    with col_b:
        if "oi_g" in panel.columns:
            oi = panel.groupby(["date", "symbol"])["oi_g"].sum().reset_index()
            fig2 = px.line(oi, x="date", y="oi_g", color="symbol",
                           template="plotly_dark", title="Daily open interest (grams)",
                           labels={"oi_g": "OI (g)", "date": ""})
            fig2.update_layout(margin=dict(t=40, b=0), height=300)
            st.plotly_chart(fig2, use_container_width=True)


def main() -> None:
    st.set_page_config(
        page_title="Edge AI -- MCX Gold Analytics",
        page_icon="\U0001f947",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(_CSS, unsafe_allow_html=True)
    if _is_synthetic():
        st.markdown(
            "<div class='synth'>"
            "\U0001f534 <strong>SYNTHETIC DATA</strong> -- "
            "All numbers are from the synthetic generator and do not represent real MCX prices. "
            "Paste your MCX cURL into <code>docs/bhavcopy_request.curl</code>, "
            "then click <b>Fetch Today &amp; Rebuild</b> in the sidebar to load real data."
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div class='live-badge'>"
            "\U0001f7e2 <strong>LIVE MCX DATA</strong> -- "
            f"Showing real MCX Bhavcopy data. Latest: <b>{_latest_date()}</b>. "
            "Use the sidebar to refresh."
            "</div>",
            unsafe_allow_html=True,
        )
    page = _sidebar()
    {
        "Parity Monitor": _page_parity,
        "Curve & Carry":  _page_curve,
        "Lifecycle":      _page_lifecycle,
        "Alerts":         _page_alerts,
        "Backtest Lab":   _page_backtest,
        "Data Health":    _page_health,
    }.get(page, _page_parity)()


if __name__ == "__main__":
    main()
