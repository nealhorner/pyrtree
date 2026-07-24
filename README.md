# pyrtree

A pure Python R-Tree spatial index implementation with zero dependencies. The current version only implements a 2-dimensional index.

A faster Python implementation with a libspatialindex dependancies is [rtree](https://github.com/Toblerity/rtree).

This project was originally taken from Dan Shoutis's [pyrtree](https://code.google.com/archive/p/pyrtree/source/default/source) project and then forked from [Rhoana's pyrtree](https://github.com/Rhoana/pyrtree).

## Usage

See [doc/USAGE.md](doc/USAGE.md) for a full usage guide.

### API
```
from pyrtree import RTree,Rect

... inserting: 
t = RTree()
t.insert(some_kind_of_object,Rect(min_x,min_y,max_x,max_y))

... querying:
point_res = t.query_point( (x,y) )
rect_res = t.query_rect( Rect(x,y,xx,yy) )

```
IMPORTANT: Query results include intermediate nodes which are invalidated as they get iterated over: so if you only want your leaf objects back: (a near-future TODO: a convenience wrapper) real_point_res = [r.leaf_obj() for r in t.query_point( (x,y) ) if r.is_leaf()] ```

## What is an RTree?
An R-tree is a spatial index over axis-aligned rectangles. (The sides of the rectangles are parallel to the X and Y axes.) They're used heavily in GIS as a way to index geospatial data.

They take the form of trees of rectangles where each node's rectangle contains the rectangle of all its children. The challenge is in deciding how to group rectangles in order to arrive at a well-balanced tree; pyrtree uses k-means clustering to do this. (S. Brakatsoulas, D. Pfoser, and Y. Theodoridis. "Revisiting R-Tree Construction Principles", Advances in Databases and Information Systems 2435 (2002): 17-24)

## Development

Requires Python >= 3.10 (developed and tested against 3.14) and [uv](https://docs.astral.sh/uv/).

```shell
uv sync --extra dev      # install dev dependencies (pytest, ruff) into .venv
uv run pytest            # run the test suite
uv run ruff check .      # lint
uv run ruff format .     # format
```

Install the git hooks with [pre-commit](https://pre-commit.com/) to run lint and format checks
automatically before each commit:

```shell
uv tool install pre-commit  # or: pip install pre-commit
pre-commit install
```

The `bench_libspatial.py` benchmark compares against the `Rtree` package, which wraps the
libspatialindex C library. It's an optional extra since it needs that system library installed:

```shell
uv sync --extra bench-compare
```

## Performance

pyrtree is pure Python, so it trades raw throughput for having no C dependencies and full
access to internal tree nodes. As a rough guide, on an Apple M1 Max (Python 3.14), inserting
50,000 randomly-sized rectangles scattered over a 1000x1000 area and then querying them gives:

| Operation      | Throughput          | Latency      |
|----------------|----------------------|--------------|
| Insert         | ~19,000 inserts/sec  | ~53 us/insert |
| Point query    | ~10,300 queries/sec  | ~97 us/query |
| Rect query     | ~6,300 queries/sec   | ~160 us/query |

Actual performance depends heavily on your hardware, Python version, and the size/distribution 
of the rectangles you're indexing. Query latency in particular grows with how much of the tree 
a given query overlaps.

To benchmark on your own machine and data:

```shell
uv run python pyrtree/bench/bench_rtree.py            # insert-only throughput over time
uv run bin/gitbench.sh                                # working tree vs. last commit
```

If you want a C-library baseline for comparison, install the `bench-compare` extra and run
`bench_libspatial.py` (see above) -- expect libspatialindex to be significantly faster.
