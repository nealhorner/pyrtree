# pyrtree Usage Guide

`pyrtree` is a pure-Python implementation of an R-Tree spatial index. It has no
C library dependencies, exposes internal nodes for custom traversal, and is
aimed at in-memory **insert/delete-then-query** workloads over 2-dimensional
data (persistence to disk is not supported).

## Installation

`pyrtree` uses [uv](https://docs.astral.sh/uv/) and a standard `pyproject.toml`
(requires Python >= 3.10).

```bash
uv sync --extra dev      # install pyrtree + dev dependencies (pytest, ruff) into .venv
```

Or install it as a regular dependency with pip:

```bash
python -m pip install .
```

## Quick Start

```python
from pyrtree import RTree, Rect

t = RTree()

# Insert an object under a unique key, with its bounding rectangle:
# Rect(min_x, min_y, max_x, max_y)
t.insert("my key", "my object", Rect(0, 0, 10, 10))
```

## Core Concepts

### `Rect`

A `Rect` represents an axis-aligned bounding box and is the unit of geometry
used throughout the index.

```python
from pyrtree import Rect

r = Rect(min_x, min_y, max_x, max_y)
```

Useful `Rect` methods:

| Method | Description |
| --- | --- |
| `r.coords()` | Returns `(x, y, xx, yy)` — the min/max coordinates. |
| `r.extent()` | Returns `(x, y, width, height)`. |
| `r.area()` | Area of the rectangle. |
| `r.union(other)` | Returns the smallest `Rect` containing both rectangles. |
| `r.union_point((x, y))` | Returns the union of the rectangle with a point. |
| `r.intersect(other)` | Returns the intersection `Rect` (or `NullRect` if disjoint). |
| `r.does_intersect(other)` | `True` if the rectangles overlap. |
| `r.does_contain(other)` | `True` if `other` is fully contained. |
| `r.does_containpoint((x, y))` | `True` if the point lies within the rectangle. |
| `r.grow(amount)` | Returns a rectangle expanded by `amount` on all sides. |
| `r.diagonal()` | Length of the rectangle's diagonal. |

### `RTree`

`RTree` is the spatial index itself. Internally it stores rectangles and
node relationships in flat arrays for performance and keeps inserted objects
in a separate object pool.

## Inserting Objects

```python
from pyrtree import RTree, Rect

t = RTree()
t.insert(some_key, some_object, Rect(min_x, min_y, max_x, max_y))
```

- `some_key` identifies this item for later removal via `delete_by_key()`.
  It must be unique among items currently in the index (checked with a dict
  lookup) -- inserting a key that's already present raises `ValueError`
  rather than silently overwriting the existing entry. Any hashable value
  works: an integer id, a string, a tuple, etc.
- `some_object` can be any Python object — it is stored as-is and returned
  from queries.
- The tree automatically rebalances (using k-means clustering of child
  rectangles) whenever a node overflows `MAXCHILDREN` (10) children.

## Deleting Objects

```python
t.delete_by_key(some_key)
```

- Looks up the key directly (no rectangle needed, and no tree descent from
  the root): the leaf's parent is found in O(1) and only that parent's own
  children (at most `MAXCHILDREN`) are scanned to unlink it.
- Returns `True` if `some_key` was present and its leaf was removed, `False`
  otherwise.
- Ancestor bounding rectangles are left as-is rather than shrunk back down
  after a delete -- they stay correct (if a little looser than optimal),
  since a superset of the true bounds still safely prunes queries.
- There's no in-place update: to move or resize an entry, `delete_by_key()`
  it and `insert()` it again (optionally reusing the same key, once it's
  been freed up by the delete).

## Querying

### Query by point

Returns every node whose rectangle contains the given point:

```python
results = t.query_point((x, y))
```

### Query by rectangle

Returns every node whose rectangle intersects the given rectangle:

```python
results = t.query_rect(Rect(x, y, xx, yy))
```

### Working with query results

Both query methods are generators that yield **tree nodes**, not just your
original objects. Nodes can be either leaves (holding your inserted object)
or internal nodes (holding a group of children), so you should filter for
leaves before pulling out your data:

```python
leaf_objects = [n.leaf_obj() for n in t.query_point((x, y)) if n.is_leaf()]
```

| Node method | Description |
| --- | --- |
| `n.is_leaf()` | `True` if this node is a leaf (wraps an inserted object). |
| `n.leaf_obj()` | Returns the original inserted object (leaves only). |
| `n.rect` | The node's bounding `Rect`. |
| `n.has_children()` / `n.children()` | Inspect an internal node's children. |

> **Note:** Query result nodes are transient cursors — the same node object
> is reused and mutated as iteration proceeds. Extract any data you need
> (e.g. via `leaf_obj()`) while you're still consuming the generator; don't
> collect raw nodes into a list to use afterward. It's safe to stop
> iterating early (`break`, `next()`, `any()`, `itertools.islice`, etc.) —
> partially consuming a query or `walk()` no longer corrupts the tree for
> subsequent operations.

## Custom Traversal

Because internal nodes are accessible, you can walk the tree yourself with a
predicate function:

```python
def predicate(node, leaf_obj):
    return node.rect.does_intersect(my_rect)


for node in t.walk(predicate):
    if node.is_leaf():
        print(node.leaf_obj())
```

`walk` yields every node (leaf or internal) for which `predicate` returns
truthy, recursing into children only when the predicate matches.

## Full Example

```python
from pyrtree import RTree, Rect

t = RTree()

# Insert a handful of labeled rectangles (using the label as its own key).
t.insert("a", "a", Rect(0, 0, 2, 2))
t.insert("b", "b", Rect(5, 5, 8, 8))
t.insert("c", "c", Rect(1, 1, 3, 3))

# Point query: what covers (1.5, 1.5)?
hits = [n.leaf_obj() for n in t.query_point((1.5, 1.5)) if n.is_leaf()]
print(hits)  # ['a', 'c'] (order not guaranteed)

# Rectangle query: what intersects this region?
region = Rect(0, 0, 4, 4)
hits = [n.leaf_obj() for n in t.query_rect(region) if n.is_leaf()]
print(hits)  # ['a', 'c'] (order not guaranteed)

# Delete by key.
t.delete_by_key("b")
hits = [n.leaf_obj() for n in t.query_rect(region) if n.is_leaf()]
print(hits)  # ['a', 'c'] -- "b" never overlapped `region` anyway
```

## Limitations

- **2D only** — the index supports two-dimensional rectangles.
- **No update** — there is no API for moving/resizing an existing entry
  in-place; delete it and re-insert instead.
- **In-memory only** — there is currently no way to persist an index to disk.

## Running Tests

```bash
uv run pytest            # run the test suite
uv run ruff check .      # lint
uv run ruff format .     # format
```

## Benchmarks

Benchmark scripts live under [pyrtree/bench](../pyrtree/bench):

```bash
python pyrtree/bench/bench_rtree.py
```

Environment variables `TEST_ITER` and `TEST_INTERVAL` control the number of
insertions and logging interval.

Convenience wrappers live under [bin](../bin):

- `bin/gitbench.sh` — benchmarks the working tree against the last commit
  and plots both with `bview.py`.
- `bin/bench_cprofile.sh` — profiles `bench_rtree.py` with `cProfile`.
- `bin/spatial_index_bench.sh` — benchmarks `libspatialindex`'s `Rtree`
  package for comparison; requires the `bench-compare` extra
  (`uv sync --extra bench-compare`) plus a local `libspatialindex` build.
