--
inclusion: always
---
# Technology

- Python 3.11+. Packages: pandas, numpy, scipy, statsmodels, pyarrow, pydantic, pyyaml, requests, typer, plotly, streamlit, pytest, ruff. DuckDB is optional.
- Package name `edge_ai` (console script `edge-ai`), src layout, installable with `pip install -e .`.
- One CLI: `python -m edge_ai <command>`. Commands are listed in the design.
- All thresholds and contract constants live in `configs/default.yaml`, validated by pydantic. No magic numbers in code.
- Dates are parsed with explicit formats only: `%m/%d/%Y` for the response Date, `%d%b%Y` for ExpiryDate, `%d/%m/%Y` for requests. Never use `dayfirst` or format inference.
- Randomness (bootstrap, placebo, synthetic data) uses a seeded `numpy.random.Generator`; the seed is in config.
- Raw data is immutable. Every derived artifact can be rebuilt from `data/raw` with one command.
- Network access happens only inside `fetch.py`. Everything else is offline and deterministic.
- Style: type hints, small pure functions, docstrings that state the formula. No notebooks in the pipeline.
- A task is done only when `pytest -q` passes and `ruff check` is clean.