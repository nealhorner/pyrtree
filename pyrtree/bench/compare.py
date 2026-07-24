"""Compare two ``regression.py`` result files and flag wall-clock regressions.

    python -m pyrtree.bench.compare base.json pr.json [--tolerance 0.15]

Exits non-zero if any metric in the PR results is slower than the base by more
than the tolerance (default 15%).  The CI job that runs this is marked
non-blocking, so a non-zero exit surfaces as a visible warning on the PR
without gating merge -- the intent is to inform a human, not to fail on noise.
"""

import argparse
import json
import sys

METRICS = [
    ("insert_us_per_op", "insert (us/op)"),
    ("query_point_us_per_query", "query_point (us/query)"),
    ("query_rect_us_per_query", "query_rect (us/query)"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base", help="baseline JSON (base branch)")
    ap.add_argument("pr", help="candidate JSON (PR branch)")
    ap.add_argument("--tolerance", type=float, default=0.15, help="allowed slowdown fraction")
    args = ap.parse_args()

    with open(args.base) as f:
        base = json.load(f)
    with open(args.pr) as f:
        pr = json.load(f)

    print(f"{'metric':<26} {'base':>10} {'pr':>10} {'delta':>9}")
    print("-" * 58)

    regressed = []
    for key, label in METRICS:
        b, p = base[key], pr[key]
        ratio = p / b if b else float("inf")
        delta_pct = (ratio - 1.0) * 100.0
        flag = ""
        if ratio > 1.0 + args.tolerance:
            flag = "  <-- REGRESSION"
            regressed.append((label, delta_pct))
        print(f"{label:<26} {b:>10.2f} {p:>10.2f} {delta_pct:>+8.1f}%{flag}")

    if regressed:
        print(
            f"\n{len(regressed)} metric(s) slower than base by more than "
            f"{args.tolerance * 100:.0f}%:"
        )
        for label, delta_pct in regressed:
            print(f"  - {label}: {delta_pct:+.1f}%")
        sys.exit(1)

    print(f"\nNo metric slower than base by more than {args.tolerance * 100:.0f}%.")


if __name__ == "__main__":
    main()
