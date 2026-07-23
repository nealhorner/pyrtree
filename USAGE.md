# pyrtree Usage Guide

`pyrtree` is a pure-Python implementation of an R-Tree spatial index. It has no
C library dependencies, exposes internal nodes for custom traversal, and is
aimed at in-memory **insert-then-query** workloads over 2-dimensional data
(updates and persistence are not supported).

## Installation

```bash
python setup.py install
```

## Quick Start

```python
from pyrtree import RTree, Rect

t = RTree()

# Insert an object with its bounding rectangle: Rect(min_x, min_y, max_x, max_y)
t.insert("my object", Rect(0, 0, 10, 10))
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
t.insert(some_object, Rect(min_x, min_y, max_x, max_y))
```

- `some_object` can be any Python object — it is stored as-is and returned
  from queries.
- The tree automatically rebalances (using k-means clustering of child
  rectangles) whenever a node overflows `MAXCHILDREN` (10) children.

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

> **Note:** Query result nodes are transient cursors — they are invalidated
> as you continue iterating past them. Extract any data you need (e.g. via
> `leaf_obj()`) while you're still consuming the generator; don't collect
> raw nodes into a list to use afterward.

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

# Insert a handful of labeled rectangles.
t.insert("a", Rect(0, 0, 2, 2))
t.insert("b", Rect(5, 5, 8, 8))
t.insert("c", Rect(1, 1, 3, 3))

# Point query: what covers (1.5, 1.5)?
hits = [n.leaf_obj() for n in t.query_point((1.5, 1.5)) if n.is_leaf()]
print(hits)  # ['a', 'c'] (order not guaranteed)

# Rectangle query: what intersects this region?
region = Rect(0, 0, 4, 4)
hits = [n.leaf_obj() for n in t.query_rect(region) if n.is_leaf()]
print(hits)  # ['a', 'c'] (order not guaranteed)
```

## Limitations

- **2D only** — the index only supports two-dimensional rectangles.
- **Insert-only** — there is no API for deleting or updating entries.
- **In-memory only** — there is currently no way to persist an index to disk.

## Running Tests

```bash
cd pyrtree/tests
python test_rtree.py
```

## Benchmarks

Benchmark scripts live under [pyrtree/bench](pyrtree/bench) and shell wrappers
under [bin](bin):

```bash
bin/spatial_index_bench.sh
```

Environment variables `TEST_ITER` and `TEST_INTERVAL` control the number of
insertions and logging interval for `pyrtree/bench/bench_rtree.py`.
