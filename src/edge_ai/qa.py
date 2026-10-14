"""qa.py: QA report for the cleaned panel."""
from __future__ import annotations

import pandas as pd

from edge_ai.config import Config


def run_qa(df: pd.DataFrame, cfg: Config, extra_warnings: list[str] | None = None) -> dict:
    """Run QA checks on the cleaned panel.

    Returns a dict with keys: passed (bool), checks (list of dicts), warnings (list of str).
    Each check dict: {name, passed, n_failures, details}.
    """
    checks = []
    warnings = list(extra_warnings or [])

    def _check(name: str, mask: pd.Series, details: str = "") -> None:
        n = int(mask.sum())
        checks.append({"name": name, "passed": n == 0, "n_failures": n, "details": details})

    if df.empty:
        return {"passed": False, "checks": [], "warnings": ["Panel is empty."]}

    # Prices > 0
    _check("close > 0", df["close"] <= 0)
    _check("open > 0", df["open"] <= 0)

    # High >= Close >= Low
    _check("high >= close", df["high"] < df["close"])
    _check("close >= low", df["close"] < df["low"])
    _check("high >= low", df["high"] < df["low"])

    # days-to-expiry >= 0
    df = df.copy()
    df["dte"] = (pd.to_datetime(df["expiry"]) - pd.to_datetime(df["date"])).dt.days
    _check("dte >= 0", df["dte"] < 0)

    # Same-expiry normalized price spread <= 1% across families (on same date)
    parity_fails = 0
    for _date_val, grp in df.groupby("date"):
        for _exp_val, exp_grp in grp.groupby("expiry"):
            if len(exp_grp) < 2:
                continue
            pxs = exp_grp["px_g_fine"]
            spread = (pxs.max() - pxs.min()) / pxs.min() * 100
            if spread > 1.0:
                parity_fails += 1
    checks.append({
        "name": "same-expiry normalized price spread <= 1%",
        "passed": parity_fails == 0,
        "n_failures": parity_fails,
        "details": "pairs of (date, expiry) where spread > 1%",
    })

    passed = all(c["passed"] for c in checks)
    return {"passed": passed, "checks": checks, "warnings": warnings}


def format_qa_report(qa_result: dict) -> str:
    """Format QA result as a human-readable string."""
    lines = ["=== QA Report ===", f"Overall: {'PASS' if qa_result['passed'] else 'FAIL'}"]
    for w in qa_result.get("warnings", []):
        lines.append(f"  WARNING: {w}")
    for c in qa_result.get("checks", []):
        status = "OK" if c["passed"] else f"FAIL ({c['n_failures']} rows)"
        lines.append(f"  [{status:20s}] {c['name']}")
    return "\n".join(lines)
