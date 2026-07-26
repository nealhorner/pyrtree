"""Deterministic performance-regression guards.

These are intentionally *not* wall-clock benchmarks -- timing is far too noisy
on shared CI runners to gate a build on.  Instead they pin the *amount of work*
the core operations do, measured as the number of ``Rect`` objects allocated
over a fixed, seeded workload.  That count is machine-independent and fully
reproducible, and it is exactly what the query/insert hot-path optimizations
reduced: a regression that reintroduces per-node ``Rect`` allocation blows past
these budgets and fails the build.

Budgets sit comfortably above the counts measured on the optimized code
(insert ~64k, query_point ~6.8k, query_rect ~8.5k).  For reference, the
pre-optimization code allocated 1.45x (insert), 4.1x (query_point) and 4.0x
(query_rect) as many Rects, so genuine regressions trip the guard with a wide
margin while ordinary churn stays comfortably under it.

Wall-clock regressions that do *not* change the allocation count are caught
separately by the (non-blocking) PR-vs-base benchmark job in CI.
"""

import random
from contextlib import contextmanager

from pyrtree import RTree
from pyrtree.rect import Rect

SEED = 20240723
N = 2000  # rects inserted to build the tree under test
NQ = 500  # queries per query workload


@contextmanager
def count_rect_allocs():
    """Count every ``Rect`` instantiation inside the block.

    Patches the class object's ``__init__``, so it counts allocations from
    every import site (rtree.py holds the same class object) regardless of how
    the Rect was constructed.
    """
    counter = {"n": 0}
    original = Rect.__init__

    def counting(self, *args, **kwargs):
        counter["n"] += 1
        original(self, *args, **kwargs)

    Rect.__init__ = counting
    try:
        yield counter
    finally:
        Rect.__init__ = original


def _build_tree():
    # k_means_cluster() shuffles via the *global* RNG, so seed that too or the
    # tree shape -- and therefore the allocation count -- is nondeterministic.
    random.seed(SEED)
    rng = random.Random(SEED)
    rt = RTree()
    for i in range(N):
        x, y = rng.uniform(0, 1000), rng.uniform(0, 1000)
        w, h = rng.uniform(0, 1), rng.uniform(0, 1)
        rt.insert(i, i, Rect(x, y, x + w, y + h))
    return rt, rng


def test_insert_allocation_budget():
    with count_rect_allocs() as c:
        _build_tree()
    assert c["n"] <= 75000, f"insert allocated {c['n']} Rects (budget 75000)"


def test_query_point_allocation_budget():
    rt, rng = _build_tree()
    pts = [(rng.uniform(0, 1000), rng.uniform(0, 1000)) for _ in range(NQ)]

    with count_rect_allocs() as c:
        for p in pts:
            for node in rt.query_point(p):
                node.is_leaf()
    assert c["n"] <= 10000, f"query_point allocated {c['n']} Rects (budget 10000)"


def test_query_rect_allocation_budget():
    rt, rng = _build_tree()
    qrects = [
        Rect(x, y, x + 20, y + 20)
        for x, y in ((rng.uniform(0, 1000), rng.uniform(0, 1000)) for _ in range(NQ))
    ]

    with count_rect_allocs() as c:
        for q in qrects:
            for node in rt.query_rect(q):
                node.is_leaf()
    assert c["n"] <= 11000, f"query_rect allocated {c['n']} Rects (budget 11000)"
