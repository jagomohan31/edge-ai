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
    """Write a markdown report containing only pipeline-computed numbers."""
    lines = [
        "# Edge AI — Pipeline Report",
        "",
        "All numbers below are computed by the pipeline. No values are hard-coded.",
        "",
        "## Attribution Waterfall",
        f"- Gross spread P&L: ₹{attribution.get('gross_pnl', float('nan')):.2f}",
        f"- Gold-price P&L (beta attribution): ₹{attribution.get('gold_pnl', float('nan')):.2f}",
        f"- Total costs: ₹{attribution.get('total_costs', float('nan')):.2f}",
        f"- **Net strategy P&L: ₹{attribution.get('net_pnl', float('nan')):.2f}**",
        "",
        "## Gold Regression",
        f"- Alpha: {attribution.get('alpha', float('nan')):.4f} (SE: {attribution.get('alpha_se', float('nan')):.4f})",
        f"- Beta: {attribution.get('beta', float('nan')):.4f} (SE: {attribution.get('beta_se', float('nan')):.4f})",
        f"- N trades: {attribution.get('n_trades', 0)}",
        "",
        "## Bootstrap CI (mean net P&L per trade)",
        f"- Mean: ₹{bootstrap.get('mean', float('nan')):.2f}",
        f"- 95% CI: [₹{bootstrap.get('ci_low', float('nan')):.2f}, ₹{bootstrap.get('ci_high', float('nan')):.2f}]",
        "",
        "## Placebo Test",
        f"- Actual mean: ₹{placebo.get('actual_mean', float('nan')):.2f}",
        f"- Placebo mean: ₹{placebo.get('placebo_mean', float('nan')):.2f}",
        f"- p-value: {placebo.get('p_value', float('nan')):.3f}",
        "",
        "## Slippage Stress",
    ]
    if slippage_df is not None and not slippage_df.empty:
        for _, row in slippage_df.iterrows():
            lines.append(f"- {row['slippage_multiplier']}x slippage: ₹{row['net_pnl']:.2f}")
    lines.append("")
    report = "\n".join(lines)

    if output_path:
        Path(output_path).write_text(report, encoding="utf-8")

    return report
