"""Wall-clock benchmark for the core operations, emitting machine-readable JSON.

Used by the CI benchmark job, which runs this once against the PR branch and
once against the base branch *on the same runner*, then diffs the results with
``compare.py``.  Running both halves on one machine cancels most runner-to-
runner noise, which is what makes a wall-clock comparison usable in CI at all.

Each metric is the best (minimum) of several repeats -- the minimum is the
least noise-contaminated estimate of the true cost.

Usage:
    python -m pyrtree.bench.regression --out results.json
"""

import argparse
import gc
import json
import random
import time

from pyrtree.rect import Rect
from pyrtree.rtree import RTree

SEED = 20240723
N = 20000  # tree size
NQ = 5000  # queries per timed workload
REPEATS = 5


def _make_rects(rng, n, size):
    out = []
    for _ in range(n):
        x, y = rng.uniform(0, 1000), rng.uniform(0, 1000)
        w, h = rng.uniform(0, size), rng.uniform(0, size)
        out.append(Rect(x, y, x + w, y + h))
    return out


def _build(rects):
    random.seed(SEED)  # k-means uses the global RNG
    rt = RTree()
    for i, r in enumerate(rects):
        rt.insert(i, r)
    return rt


def _best(fn):
    best = float("inf")
    for _ in range(REPEATS):
        t = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - t)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="path to write JSON results")
    ap.add_argument("--label", default="", help="optional label recorded in the output")
    args = ap.parse_args()

    gc.disable()
    rng = random.Random(SEED)
    rects = _make_rects(rng, N, size=1.0)

    # insert: rebuild the whole tree each repeat.
    insert_best = _best(lambda: _build(rects))

    rt = _build(rects)
    pts = [(rng.uniform(0, 1000), rng.uniform(0, 1000)) for _ in range(NQ)]
    qrects = [Rect(q.x, q.y, q.x + 20, q.y + 20) for q in _make_rects(rng, NQ, size=1.0)]

    def run_point():
        for p in pts:
            for node in rt.query_point(p):
                node.is_leaf()

    def run_rect():
        for q in qrects:
            for node in rt.query_rect(q):
                node.is_leaf()

    point_best = _best(run_point)
    rect_best = _best(run_rect)

    results = {
        "label": args.label,
        "insert_us_per_op": insert_best / N * 1e6,
        "query_point_us_per_query": point_best / NQ * 1e6,
        "query_rect_us_per_query": rect_best / NQ * 1e6,
    }
    with open(args.out, "w") as f:
        json.dump(results, f, indent=2)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
