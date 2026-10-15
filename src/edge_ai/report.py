"""report.py: one-page pipeline-computed markdown summary (Req 8.4)."""
from __future__ import annotations

from pathlib import Path


def write_report(
    attribution: dict,
    bootstrap: dict,
    placebo: dict,
    slippage_df,
    output_path: Path | None = None,
) -> str:
    """Write a markdown report containing only pipeline-computed numbers.

    attribution keys: gross, gold, relative_value, costs, net, beta_fine_grams, beta_se, r2, n_trades
    bootstrap keys: mean, ci_low, ci_high, n_trades
    placebo keys: actual_mean, placebo_mean, p_value
    slippage_df: DataFrame with slippage_multiplier, net_pnl columns
    """
    nan = float("nan")
    gross = attribution.get("gross", attribution.get("gross_pnl", nan))
    gold  = attribution.get("gold",  attribution.get("gold_pnl",  nan))
    costs = attribution.get("costs", attribution.get("total_costs", nan))
    net   = attribution.get("net",   attribution.get("net_pnl",   nan))
    beta  = attribution.get("beta_fine_grams", attribution.get("beta", nan))
    beta_se = attribution.get("beta_se", nan)
    r2    = attribution.get("r2", nan)
    n     = attribution.get("n_trades", 0)

    lines = [
        "# Edge AI - Pipeline Report",
        "",
        "All numbers below are computed by the pipeline. No values are hard-coded.",
        "",
        "## Attribution Waterfall",
        f"- Gross spread P&L: Rs{gross:.2f}",
        f"- Gold-price P&L (beta attribution): Rs{gold:.2f}",
        f"- Relative-value P&L: Rs{gross - gold:.2f}" if gross == gross and gold == gold else "- Relative-value P&L: n/a",
        f"- Total costs: Rs{costs:.2f}",
        f"- **Net strategy P&L: Rs{net:.2f}**",
        "",
        "## Gold Regression",
        f"- Beta (fine grams): {beta:.4f} (SE: {beta_se:.4f})",
        f"- R-squared: {r2:.4f}",
        f"- N trades: {n}",
        "",
        "## Bootstrap CI (mean net P&L per trade)",
        f"- Mean: Rs{bootstrap.get('mean', nan):.2f}",
        f"- 95% CI: [Rs{bootstrap.get('ci_low', nan):.2f}, Rs{bootstrap.get('ci_high', nan):.2f}]",
        "",
        "## Placebo Test",
        f"- Actual mean: Rs{placebo.get('actual_mean', nan):.2f}",
        f"- Placebo mean: Rs{placebo.get('placebo_mean', nan):.2f}",
        f"- p-value: {placebo.get('p_value', nan):.3f}",
        "",
        "## Slippage Stress",
    ]
    if slippage_df is not None and not slippage_df.empty:
        for _, row in slippage_df.iterrows():
            lines.append(f"- {row['slippage_multiplier']}x slippage: Rs{row['net_pnl']:.2f}")
    lines.append("")
    report = "\n".join(lines)

    if output_path:
        Path(output_path).write_text(report, encoding="utf-8")

    return report
