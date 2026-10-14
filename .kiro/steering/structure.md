--
inclusion: always
---
# Project structure

```
edge-ai/
+- .kiro/            steering + specs        .agent/   rules + workflows
+- configs/default.yaml
+- data/raw/         one parquet per requested date, plus .skip markers (immutable)
+- data/clean/       panel.parquet
+- data/derived/     factor.parquet, curves.parquet, gaps.parquet, lifecycle.parquet
+- docs/             bhavcopy_request.curl, METHOD.md, LIMITATIONS.md
+- runs/             trials.csv, <run_id>/ (trades, equity, attribution, summary.json)
+- src/edge_ai/
|   +- cli.py config.py spec.py synthetic.py
|   +- fetch.py clean.py qa.py panel.py
|   +- normalize.py curve.py lifecycle.py
|   +- liquidity.py costs.py signals.py
|   +- backtest.py attribution.py stats.py report.py
|   +- app/dashboard.py, app/pages/
+- tests/            unit, property and golden tests
+- pyproject.toml  Makefile  README.md
```

Conventions: one module per concern, no circular imports, pure functions take DataFrames and a config object, artifacts are written only by the CLI layer, the dashboard reads artifacts and never recomputes.