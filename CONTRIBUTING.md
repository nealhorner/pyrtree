# Contributing to pyrtree

Thanks for your interest in improving pyrtree. This guide covers everything you need to get set
up and submit a change.

## Getting set up

Requires Python >= 3.10 (CI covers 3.10, 3.12, and 3.14) and [uv](https://docs.astral.sh/uv/).

```shell
uv sync --extra dev      # install dev dependencies (pytest, ruff) into .venv
uv run pytest            # run the test suite
uv run ruff check .      # lint
uv run ruff format .     # format
```

Install the git hooks with [pre-commit](https://pre-commit.com/) so lint and format checks run
automatically before each commit:

```shell
uv tool install pre-commit  # or: pip install pre-commit
pre-commit install
```

## Project layout

- [pyrtree/rtree.py](pyrtree/rtree.py) and [pyrtree/rect.py](pyrtree/rect.py) — the core index
  implementation.
- [pyrtree/tests](pyrtree/tests) — the test suite (`test_rtree.py`, `test_perf.py`).
- [pyrtree/bench](pyrtree/bench) — benchmark scripts (throughput and regression comparisons).
- [doc/USAGE.md](doc/USAGE.md) — the usage guide; update it if you change public behavior.
- [bin/](bin) — shell helpers for running benchmarks locally.

## Making a change

1. Create a branch off `master`.
2. Make your change, keeping it focused — avoid unrelated refactors in the same PR.
3. Add or update tests in `pyrtree/tests` for any behavior change. `test_perf.py` contains
   deterministic perf-budget guards; if your change affects hot paths, make sure these still pass
   and adjust the budgets only with justification.
4. Update [doc/USAGE.md](doc/USAGE.md) or the README if you change the public API or documented
   behavior.
5. Run the full check suite locally before pushing:

   ```shell
   uv run ruff check .
   uv run ruff format --check .
   uv run pytest
   ```

6. **Bump the version** in [pyproject.toml](pyproject.toml). CI enforces that every PR increments
   `version` relative to the base branch — the `version-check` job in
   [.github/workflows/pr-checks.yml](.github/workflows/pr-checks.yml) will fail the PR otherwise.
   Use your judgment on patch vs. minor bump based on the size of the change.
7. If you changed dependencies or Python version support, regenerate the lockfile with
   `uv lock`.

## Performance

pyrtree's value proposition is "pure Python, no C dependencies, still reasonably fast," so
performance is treated as a first-class concern:

- `pyrtree/tests/test_perf.py` enforces deterministic perf budgets as part of the normal test run.
- On every PR, CI also runs a non-blocking benchmark comparison (`benchmark` job in
  [.github/workflows/ci.yml](.github/workflows/ci.yml)) that measures your branch against the PR's
  base commit and flags regressions greater than 15%. This job is informational and won't block
  merge, but please look at it if it flags something.
- To benchmark locally:

  ```shell
  uv run python pyrtree/bench/bench_rtree.py   # insert-only throughput over time
  uv run bin/gitbench.sh                        # working tree vs. last commit
  ```

If you want a C-library baseline for comparison, install the `bench-compare` extra
(`uv sync --extra bench-compare`) and run `bench_libspatial.py`.

## Code style

- Formatting and linting are handled by [ruff](https://docs.astral.sh/ruff/) (`ruff check` /
  `ruff format`), configured in [pyproject.toml](pyproject.toml). Line length is 100.
- No enforced docstring style; prefer clear naming over comments, and reserve comments for
  non-obvious "why" (e.g. a subtle invariant or workaround), not restating what the code does.

## Submitting a pull request

- Open the PR against `master`.
- CI (`.github/workflows/ci.yml` and `pr-checks.yml`) runs lint, formatting, tests across
  supported Python versions, and the version-check gate described above — all must pass except
  the informational benchmark job.
- Describe the "why" behind the change in the PR description, not just the "what."

## Reporting issues

If you find a bug or have a feature request, please open a GitHub issue with a minimal
reproduction where possible (input rectangles/points and the query that misbehaves are usually
enough).
