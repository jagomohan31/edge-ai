"""tests/test_stats2.py: bootstrap CI test ported from reference."""
from __future__ import annotations

import numpy as np

from edge_ai.stats import bootstrap_ci


def test_bootstrap_ci_is_seeded_and_brackets_the_mean():
    x = np.random.default_rng(3).normal(5, 2, 200)
    lo, hi = bootstrap_ci(x, n=2000, seed=7)
    assert lo < x.mean() < hi
    # seeded: same result on repeat
    assert (lo, hi) == bootstrap_ci(x, n=2000, seed=7)
    # degenerate: all same value
    assert bootstrap_ci([4.0, 4.0, 4.0], n=100) == (4.0, 4.0)
