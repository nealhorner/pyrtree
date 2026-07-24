# pyrtree
An R-Tree implementation

Taken from https://code.google.com/archive/p/pyrtree/source/default/source
(No way to automatically move the versioned source code from code.google.com, so this is copied)

See [doc/USAGE.md](doc/USAGE.md) for a full usage guide.

Here's the original project description (https://code.google.com/archive/p/pyrtree/):

# pyrtree
This is a pure python implementation of an RTree spatial index -- with no C library dependencies while retaining decent performance.

I wrote it with the following reasons in mind: * Pure cross-platform python; no C library dependencies. * Access to internal nodes in the tree, allowing for custom traversal strategies. * BSD license

The current version targets in-memory insert-then-query workloads -- updates and persistence are not implemented yet -- and performs quite well at doing so. Besides those limitations, the current version only implements a 2-dimensional index. I'm not sure if this will change: R-tree performance drops quickly as you add dimensions, and I anticipate the largest uses of this library will be by GIS developers, where two-dimensional datasets are king. Planned enhancement: saving and loading the index to disk.

# API
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


# What is an RTree?
An R-tree is a spatial index over axis-aligned rectangles. (The sides of the rectangles are parallel to the X and Y axes.) They're used heavily in GIS as a way to index geospatial data.

They take the form of trees of rectangles where each node's rectangle contains the rectangle of all its children. The challenge is in deciding how to group rectangles in order to arrive at a well-balanced tree; pyrtree uses k-means clustering to do this. (S. Brakatsoulas, D. Pfoser, and Y. Theodoridis. "Revisiting R-Tree Construction Principles", Advances in Databases and Information Systems 2435 (2002): 17-24)

# Development

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

# Performance

pyrtree is pure Python, so it trades raw throughput for having no C dependencies and full
access to internal tree nodes. As a rough guide, on an Apple M1 Max (Python 3.14), inserting
50,000 randomly-sized rectangles scattered over a 1000x1000 area and then querying them gives:

| Operation      | Throughput          | Latency      |
|----------------|----------------------|--------------|
| Insert         | ~15,800 inserts/sec  | ~63 us/insert |
| Point query    | ~4,700 queries/sec   | ~213 us/query |
| Rect query     | ~3,000 queries/sec   | ~336 us/query |

These numbers are illustrative, not guarantees -- actual performance depends heavily on your
hardware, Python version, and the size/distribution of the rectangles you're indexing. Query
latency in particular grows with how much of the tree a given query overlaps.

To benchmark on your own machine and data:

```shell
uv run python pyrtree/bench/bench_rtree.py            # insert-only throughput over time
uv run bin/gitbench.sh                                 # working tree vs. last commit
```

If you want a C-library baseline for comparison, install the `bench-compare` extra and run
`bench_libspatial.py` (see above) -- expect libspatialindex to be significantly faster for
large datasets, since it isn't paying Python's per-object overhead.

