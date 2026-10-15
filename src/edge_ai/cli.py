"""cli.py: Edge AI command-line interface."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import typer

app = typer.Typer(help="Edge AI: MCX gold futures relative-value analytics.")


def _load_cfg(config: Path | None = None):
    from edge_ai.config import load_config
    return load_config(config)


@app.command()
def fetch(
    start: str = typer.Option(..., help="Start date YYYY-MM-DD"),  # noqa: B008
    end: str = typer.Option(..., help="End date YYYY-MM-DD"),  # noqa: B008
    curl_file: Path | None = typer.Option(None, help="Path to bhavcopy_request.curl"),  # noqa: B008
    config: Path | None = typer.Option(None, help="Config YAML path"),  # noqa: B008
) -> None:
    """Fetch Bhavcopy data for a date range."""
    from edge_ai.fetch import fetch_range
    cfg = _load_cfg(config)
    s = date.fromisoformat(start)
    e = date.fromisoformat(end)
    results = fetch_range(s, e, cfg, curl_path=curl_file)
    for day, status in sorted(results.items()):
        typer.echo(f"  {day}: {status}")


@app.command()
def clean(config: Path | None = typer.Option(None)) -> None:  # noqa: B008
    """Clean raw data and print QA report."""
    from edge_ai.clean import clean as do_clean
    from edge_ai.clean import load_raw
    from edge_ai.qa import format_qa_report, run_qa
    cfg = _load_cfg(config)
    raw_df = load_raw(Path(cfg.data.raw_dir))
    df, warnings = do_clean(raw_df, cfg)
    qa_result = run_qa(df, cfg, warnings)
    typer.echo(format_qa_report(qa_result))


@app.command()
def build(config: Path | None = typer.Option(None)) -> None:  # noqa: B008
    """Build panel.parquet and lifecycle.parquet."""
    from edge_ai.lifecycle import compute_lifecycle
    from edge_ai.panel import build_panel
    cfg = _load_cfg(config)
    panel = build_panel(cfg, save=True)
    lc = compute_lifecycle(panel, cfg)
    out = Path(cfg.data.derived_dir)
    out.mkdir(parents=True, exist_ok=True)
    lc.to_parquet(out / "lifecycle.parquet", index=False)
    typer.echo(f"Lifecycle saved: {len(lc)} contracts")


@app.command()
def analyze(config: Path | None = typer.Option(None)) -> None:  # noqa: B008
    """Compute curves, factor, gaps."""
    from edge_ai.curve import compute_curves, compute_gold_factor
    from edge_ai.normalize import build_gaps
    cfg = _load_cfg(config)
    panel = _load_panel(cfg)
    curves = compute_curves(panel, cfg)
    factor = compute_gold_factor(curves, cfg)
    gaps = build_gaps(panel, cfg)
    out = Path(cfg.data.derived_dir)
    out.mkdir(parents=True, exist_ok=True)
    curves.to_parquet(out / "curves.parquet", index=False)
    factor.to_parquet(out / "factor.parquet", index=False)
    gaps.to_parquet(out / "gaps.parquet", index=False)
    typer.echo(f"Curves: {len(curves)}, Factor: {len(factor)}, Gaps: {len(gaps)}")


@app.command()
def signals(config: Path | None = typer.Option(None)) -> None:  # noqa: B008
    """Compute signals and alerts."""
    from edge_ai.signals import compute_signals
    cfg = _load_cfg(config)
    panel = _load_panel(cfg)
    sigs = compute_signals(panel, cfg)
    alerts = sigs[sigs["alert"]] if hasattr(sigs, "columns") else [r for r in sigs if r.alert]
    n_alerts = len(alerts)
    n_total = len(sigs)
    typer.echo(f"Total signals: {n_total}, Alerts: {n_alerts}, No-signal: {n_total - n_alerts}")


@app.command()
def backtest(
    window: str = typer.Option("develop", help="develop | validate | locked"),  # noqa: B008
    force: bool = typer.Option(False, help="Force re-run locked window"),  # noqa: B008
    config: Path | None = typer.Option(None),  # noqa: B008
) -> None:
    """Run the walk-forward backtest."""
    import json
    import uuid

    from edge_ai.backtest import make_px, run_window
    from edge_ai.signals import compute_signals
    cfg = _load_cfg(config)
    panel = _load_panel(cfg)
    sigs = compute_signals(panel, cfg)
    px = make_px(panel)
    trades = run_window(sigs, px, panel, cfg, window=window, force=force)
    run_id = str(uuid.uuid4())[:8]
    out = Path("runs") / run_id
    out.mkdir(parents=True, exist_ok=True)
    trades.to_parquet(out / "trades.parquet", index=False)
    # Build equity curve from trades
    equity = _build_equity_curve(trades, panel)
    equity.to_parquet(out / "equity.parquet", index=False)
    summary = {"run_id": run_id, "window": window, "n_trades": len(trades)}
    (out / "summary.json").write_text(json.dumps(summary))
    _append_trial(run_id, window, len(trades))
    net_col = "net_inr" if "net_inr" in trades.columns else ("net_pnl_inr" if "net_pnl_inr" in trades.columns else None)
    net_total = float(trades[net_col].sum()) if (net_col and not trades.empty) else 0.0
    typer.echo(f"Run {run_id}: {len(trades)} trades, net P&L: INR {net_total:.0f}")


@app.command()
def report(config: Path | None = typer.Option(None)) -> None:  # noqa: B008
    """Write one-page pipeline report."""
    from edge_ai.attribution import compute_attribution
    from edge_ai.backtest import make_px, run_window
    from edge_ai.report import write_report
    from edge_ai.signals import compute_signals
    from edge_ai.stats import bootstrap_mean_pnl, slippage_stress
    cfg = _load_cfg(config)
    panel = _load_panel(cfg)
    sigs = compute_signals(panel, cfg)
    px = make_px(panel)
    trades = run_window(sigs, px, panel, cfg, window="develop")
    attr = compute_attribution(trades, panel, cfg)
    bs = bootstrap_mean_pnl(trades, cfg)
    # Minimal placebo: compare mean to zero (full placebo_means is slow)
    pl = {
        "actual_mean": bs["mean"],
        "placebo_mean": 0.0,
        "p_value": float("nan"),
    }
    sl = slippage_stress(trades, cfg.costs.slippage_stress)
    text = write_report(attr, bs, pl, sl, Path("docs/REPORT.md"))
    typer.echo(text)


@app.command()
def rebuild(
    start: str = typer.Option(..., help="Start date YYYY-MM-DD"),  # noqa: B008
    end: str = typer.Option(..., help="End date YYYY-MM-DD"),  # noqa: B008
    config: Path | None = typer.Option(None),  # noqa: B008
) -> None:
    """Rebuild all derived artifacts from data/raw for a date range."""
    typer.echo(f"Rebuilding artifacts for {start} to {end}...")
    build(config=config)
    analyze(config=config)
    signals(config=config)
    typer.echo("Rebuild complete.")


@app.command()
def demo(config: Path | None = typer.Option(None)) -> None:  # noqa: B008
    """Run end-to-end demo with synthetic data (SYNTHETIC DATA)."""
    from edge_ai.synthetic import generate_and_save
    typer.echo("=" * 60)
    typer.echo("  SYNTHETIC DATA -- demo mode, not real MCX data  ")
    typer.echo("=" * 60)
    cfg = _load_cfg(config)
    # Generate 90 days of synthetic data
    today = date.today()
    if today.month > 3:
        gen_start = date(today.year, today.month - 3, today.day)
    else:
        gen_start = date(today.year - 1, today.month + 9, today.day)
    generate_and_save(gen_start, today, cfg, raw_dir=cfg.data.raw_dir)
    typer.echo(f"Synthetic data generated for {gen_start} to {today}")
    build(config=config)
    analyze(config=config)
    signals(config=config)
    typer.echo("Demo complete. Run `edge-ai app` to open the dashboard.")


@app.command()
def app_cmd(config: Path | None = typer.Option(None)) -> None:  # noqa: B008
    """Launch the Streamlit dashboard."""
    import subprocess
    import sys
    dashboard = Path(__file__).parent / "app" / "dashboard.py"
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(dashboard)], check=False)


# Register `app` as the command name
app.command(name="app")(app_cmd)


def _load_panel(cfg):
    import pandas as pd
    p = Path(cfg.data.clean_dir) / "panel.parquet"
    if not p.exists():
        raise RuntimeError(f"panel.parquet not found at {p}. Run `edge-ai build` first.")
    return pd.read_parquet(p)


def _load_derived(cfg, name: str):
    import pandas as pd
    p = Path(cfg.data.derived_dir) / name
    if not p.exists():
        raise RuntimeError(f"{name} not found at {p}. Run `edge-ai analyze` first.")
    return pd.read_parquet(p)


def _build_equity_curve(trades, panel):
    """Reconstruct a simple equity curve from trades DataFrame."""
    import pandas as pd
    if trades is None or trades.empty:
        dates = panel["date"].sort_values().unique()
        return pd.DataFrame({"date": dates, "portfolio_value": [1_000_000.0] * len(dates)})
    trades2 = trades.copy()
    trades2["exit_date"] = pd.to_datetime(trades2["exit_date"])
    daily = trades2.groupby("exit_date")["net_pnl_inr"].sum().sort_index()
    dates = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
    equity = daily.reindex(dates, fill_value=0.0).cumsum() + 1_000_000.0
    return pd.DataFrame({"date": equity.index, "portfolio_value": equity.values})


def _append_trial(run_id: str, window: str, n_trades: int) -> None:
    import csv
    trials = Path("runs/trials.csv")
    trials.parent.mkdir(parents=True, exist_ok=True)
    write_header = not trials.exists()
    with trials.open("a", newline="") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(["run_id", "window", "n_trades"])
        w.writerow([run_id, window, n_trades])


if __name__ == "__main__":
    app()
