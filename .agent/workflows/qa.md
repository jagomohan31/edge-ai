 QA

Run the full quality check for Edge AI and report results:
1. `ruff check` and `pytest -q`. List any failure with the file and line.
2. Run `pytest tests/test_no_lookahead.py -q` on its own and confirm it passes.
3. Run `python -m edge_ai rebuild` on a held-out date range that was not used during development and confirm every artifact regenerates without code changes.
4. Open the dashboard on synthetic data and on real data (if fetched) and confirm every page loads and the SYNTHETIC DATA banner appears only for synthetic data.
5. Check that no number in `docs/` or the README is hard-coded; each must come from `edge-ai report`.
6. Summarise: what passed, what failed, what to fix next.