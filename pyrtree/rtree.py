## R-tree.
# see doc/ref/r-tree-clustering-split-algo.pdf

import array
import random
import time

from .rect import NullRect, Rect, union_all

MAXCHILDREN = 10
MAX_KMEANS = 5


class RTree:
    def __init__(self):
        self.count = 0
        self.stats = {
            "overflow_f": 0,
            "avg_overflow_t_f": 0.0,
            "longest_overflow": 0.0,
            "longest_kmeans": 0.0,
            "sum_kmeans_iter_f": 0,
            "count_kmeans_iter_f": 0,
            "avg_kmeans_iter_f": 0.0,
        }

        # This round: not using objects directly -- they
        #   take up too much memory, and efficiency goes down the toilet
        #   (obviously) if things start to page.
        #  Less obviously: using object graph directly leads to really long GC
        #   pause times, too.
        # Instead, it uses pools of arrays:
        self.count = 0
        self.leaf_count = 0
        self.rect_pool = array.array("d")
        self.node_pool = array.array("L")
        self.node_leaf_flags = array.array("B")
        self.node_null_flags = array.array("B")
        self.node_parent_pool = array.array("L")
        self.leaf_pool = []  # leaf objects.

        # Maps a caller-supplied key to the tree-node index of its leaf, so
        # delete_by_key() can jump straight to the node's parent instead of
        # descending from the root.
        self.key_index = {}

        self.cursor = _NodeCursor.create(self, NullRect)

    def _ensure_pool(self, idx):
        if len(self.rect_pool) < (4 * idx):
            self.rect_pool.extend([0, 0, 0, 0] * idx)
            self.node_pool.extend([0, 0] * idx)
            self.node_leaf_flags.extend([0] * idx)
            self.node_null_flags.extend([0] * idx)
            self.node_parent_pool.extend([0] * idx)

    def insert(self, key, o, orect):
        """Insert `o`, bounded by `orect`, under `key`.

        `key` must be unique among currently-present items (checked with a
        dict lookup) -- it's how `delete_by_key()` finds this leaf again
        later. Raises `ValueError` if `key` is already in use; delete or
        update the existing entry first if that's what you meant.
        """
        if key in self.key_index:
            raise ValueError(f"key {key!r} is already present in the index")
        leaf_index = self.cursor.insert(o, orect)
        self.key_index[key] = leaf_index
        assert self.cursor.index == 0

    def delete_by_key(self, key):
        """Remove the item inserted under `key`.

        Returns True if `key` was present and its leaf was removed, False
        otherwise.

        Unlike matching by object/rect, this doesn't need to descend the
        tree at all: the leaf's parent is looked up directly (O(1)), and
        only that parent's own children (at most `MAXCHILDREN`) are
        scanned to unlink it. Ancestor bounding rectangles are left as-is
        rather than shrunk back down -- they stay correct (if a little
        looser than optimal) since a superset of the true bounds still
        safely prunes queries.
        """
        leaf_index = self.key_index.pop(key, None)
        if leaf_index is None:
            return False

        npool = self.node_pool
        parent_index = self.node_parent_pool[leaf_index]

        prev = 0
        ci = npool[parent_index * 2 + 1]
        while ci != 0:
            next_ci = npool[ci * 2]
            if ci == leaf_index:
                if prev == 0:
                    npool[parent_index * 2 + 1] = next_ci
                else:
                    npool[prev * 2] = next_ci
                leaf_pool_index = npool[leaf_index * 2 + 1]
                self.leaf_pool[leaf_pool_index] = None
                if parent_index == self.cursor.index:
                    # self.cursor caches its own first_child/next_sibling
                    # in Python attributes rather than reading node_pool
                    # live -- when the root is the parent we just mutated
                    # above, that cache is now stale, so refresh it. (Any
                    # other node's cursor is always freshly loaded via
                    # _load()/_become() before use, so only the persistent
                    # root cursor can go stale like this.)
                    self.cursor._become(self.cursor.index)
                return True
            prev = ci
            ci = next_ci

        # key_index and the tree should never disagree, but don't silently
        # pretend success if they somehow do.
        return False

    def query_rect(self, r):
        yield from self.cursor.lift().query_rect(r)

    def query_point(self, p):
        yield from self.cursor.lift().query_point(p)

    def walk(self, pred):
        return self.cursor.lift().walk(pred)


class _NodeCursor:
    @classmethod
    def create(cls, rooto, rect):
        idx = rooto.count
        rooto.count += 1

        rooto._ensure_pool(idx + 1)
        # rooto.node_pool.extend([0,0])
        # rooto.rect_pool.extend([0,0,0,0])

        retv = _NodeCursor(rooto, idx, rect, 0, 0)

        retv._save_back()
        return retv

    @classmethod
    def create_with_children(cls, children, rooto):
        rect = union_all([c for c in children])
        assert not rect.swapped_x
        nc = _NodeCursor.create(rooto, rect)
        nc._set_children(children)
        assert not nc.is_leaf()
        return nc

    @classmethod
    def create_leaf(cls, rooto, leaf_obj, leaf_rect):
        rect = Rect(leaf_rect.x, leaf_rect.y, leaf_rect.xx, leaf_rect.yy)
        res = _NodeCursor.create(rooto, rect)
        idx = res.index
        rooto.node_leaf_flags[idx] = 1  # Mark as leaf.
        res.first_child = rooto.leaf_count
        rooto.leaf_count += 1
        res.next_sibling = 0
        rooto.leaf_pool.append(leaf_obj)
        res._save_back()
        res._become(idx)
        assert res.is_leaf()
        return res

    __slots__ = ("root", "npool", "rpool", "index", "rect", "next_sibling", "first_child")

    def __init__(self, rooto, index, rect, first_child, next_sibling):
        self.root = rooto
        self.rpool = rooto.rect_pool
        self.npool = rooto.node_pool

        self.index = index
        self.rect = rect
        self.next_sibling = next_sibling
        self.first_child = first_child

    @classmethod
    def _load(cls, root, index):
        """Cheaply materialize the cursor sitting at 'index'."""
        c = cls(root, 0, NullRect, 0, 0)
        c._become(index)
        return c

    def walk(self, predicate):
        # Iterative (explicit stack) rather than recursive generators: a
        # recursive walk delegates through one generator per tree level, so
        # every yielded node bubbles up through O(depth) `yield from`s.  The
        # stack holds bare integer indices; a cursor is only materialized for
        # nodes we actually visit, and is_leaf/leaf_obj are computed once each
        # (the old code paid for is_leaf twice and fetched a leaf_obj the query
        # predicates never looked at).
        root = self.root
        npool = self.npool
        leaf_flags = root.node_leaf_flags
        leaf_pool = root.leaf_pool
        stack = [self.index]
        while stack:
            idx = stack.pop()
            is_leaf = leaf_flags[idx]
            c = _NodeCursor._load(root, idx)
            leaf_o = leaf_pool[c.first_child] if is_leaf else None
            if predicate(c, leaf_o):
                yield c
                if not is_leaf:
                    child = npool[idx * 2 + 1]
                    while child != 0:
                        stack.append(child)
                        child = npool[child * 2]

    def query_rect(self, r):
        """Return things that intersect with 'r'."""
        if r is NullRect:
            return

        rx, ry, rxx, ryy = r.x, r.y, r.xx, r.yy
        root = self.root
        rpool = self.rpool
        npool = self.npool
        leaf_flags = root.node_leaf_flags
        null_flags = root.node_null_flags

        # Test intersection straight against the raw coordinate pool -- no
        # per-node Rect object, and null nodes are skipped by flag (matching
        # Rect.does_intersect's NullRect short-circuit).
        stack = [self.index]
        while stack:
            idx = stack.pop()
            if null_flags[idx]:
                continue
            ri = idx * 4
            ox = rpool[ri]
            if (rxx if rxx < rpool[ri + 2] else rpool[ri + 2]) - (rx if rx > ox else ox) <= 0:
                continue
            oy = rpool[ri + 1]
            if (ryy if ryy < rpool[ri + 3] else rpool[ri + 3]) - (ry if ry > oy else oy) <= 0:
                continue

            yield _NodeCursor._load(root, idx)

            if not leaf_flags[idx]:
                child = npool[idx * 2 + 1]
                while child != 0:
                    stack.append(child)
                    child = npool[child * 2]

    def query_point(self, point):
        """Query by a point"""
        px, py = point
        root = self.root
        rpool = self.rpool
        npool = self.npool
        leaf_flags = root.node_leaf_flags

        # Raw-coordinate containment test.  Null nodes store (0,0,0,0) in the
        # pool, so this reproduces Rect.does_containpoint exactly (including the
        # origin edge case) without a special case.
        stack = [self.index]
        while stack:
            idx = stack.pop()
            ri = idx * 4
            if not (rpool[ri] <= px <= rpool[ri + 2] and rpool[ri + 1] <= py <= rpool[ri + 3]):
                continue

            yield _NodeCursor._load(root, idx)

            if not leaf_flags[idx]:
                child = npool[idx * 2 + 1]
                while child != 0:
                    stack.append(child)
                    child = npool[child * 2]

    def lift(self):
        return _NodeCursor(self.root, self.index, self.rect, self.first_child, self.next_sibling)

    def _become(self, index):
        recti = index * 4
        nodei = index * 2
        rp = self.rpool
        x = rp[recti]
        y = rp[recti + 1]
        xx = rp[recti + 2]
        yy = rp[recti + 3]

        if self.root.node_null_flags[index]:
            self.rect = NullRect
        else:
            self.rect = Rect(x, y, xx, yy)

        self.next_sibling = self.npool[nodei]
        self.first_child = self.npool[nodei + 1]
        self.index = index

    def is_leaf(self):
        return bool(self.root.node_leaf_flags[self.index])

    def has_children(self):
        return not self.is_leaf() and 0 != self.first_child

    def holds_leaves(self):
        if 0 == self.first_child:
            return True
        else:
            return self.has_children() and self.get_first_child().is_leaf()

    def get_first_child(self):
        c = _NodeCursor(self.root, 0, NullRect, 0, 0)
        c._become(self.first_child)
        return c

    def leaf_obj(self):
        if self.is_leaf():
            return self.root.leaf_pool[self.first_child]
        else:
            return None

    def _save_back(self):
        rp = self.rpool
        recti = self.index * 4
        nodei = self.index * 2

        if self.rect is not NullRect:
            self.rect.write_raw_coords(rp, recti)
            self.root.node_null_flags[self.index] = 0
        else:
            rp[recti] = 0
            rp[recti + 1] = 0
            rp[recti + 2] = 0
            rp[recti + 3] = 0
            self.root.node_null_flags[self.index] = 1

        self.npool[nodei] = self.next_sibling
        self.npool[nodei + 1] = self.first_child

    def nchildren(self):
        return sum(1 for _ in self.children())

    def insert(self, leafo, leafrect):
        """Insert leafo/leafrect and return the new leaf's tree-node index."""
        index = self.index

        # tail recursion, made into loop:
        while True:
            if self.holds_leaves():
                self.rect = self.rect.union(leafrect)
                leaf = _NodeCursor.create_leaf(self.root, leafo, leafrect)
                leaf_index = leaf.index
                self._insert_child(leaf)

                self._balance()

                # done: become the original again
                self._become(index)
                return leaf_index
            else:
                # Not holding leaves, move down a level in the tree:

                # Micro-optimization:
                #  inlining union() calls -- logic is:
                # ignored,child = min([
                #     ((c.rect.union(leafrect)).area() - c.rect.area(), c.index)
                #     for c in self.children()
                # ])
                # We walk the sibling chain straight through the pools instead
                # of via children(), which would allocate a Rect per child; the
                # descent touches every level on every insert.  leafrect's
                # coords are also hoisted out of the loop (they were re-unpacked
                # per child before).
                npool = self.npool
                rpool = self.rpool
                lx, ly, lxx, lyy = leafrect.x, leafrect.y, leafrect.xx, leafrect.yy
                child = None
                minarea = -1.0
                ci = self.first_child
                while ci != 0:
                    ri = ci * 4
                    x = rpool[ri]
                    y = rpool[ri + 1]
                    xx = rpool[ri + 2]
                    yy = rpool[ri + 3]
                    nx = x if x < lx else lx
                    nxx = xx if xx > lxx else lxx
                    ny = y if y < ly else ly
                    nyy = yy if yy > lyy else lyy
                    a = (nxx - nx) * (nyy - ny)
                    if minarea < 0 or a < minarea:
                        minarea = a
                        child = ci
                    ci = npool[ci * 2]
                # End micro-optimization

                self.rect = self.rect.union(leafrect)
                self._save_back()
                self._become(child)  # recurse.

    def _balance(self):
        if self.nchildren() <= MAXCHILDREN:
            return

        t = time.perf_counter()

        s_children = [c.lift() for c in self.children()]

        memo = {}

        clusterings = [k_means_cluster(self.root, k, s_children) for k in range(2, MAX_KMEANS)]
        scored = [(silhouette_coeff(c, memo), c) for c in clusterings]
        score, bestcluster = max(scored, key=lambda sc: sc[0])

        nodes = [_NodeCursor.create_with_children(c, self.root) for c in bestcluster if len(c) > 0]

        self._set_children(nodes)

        dur = time.perf_counter() - t
        c = float(self.root.stats["overflow_f"])
        oa = self.root.stats["avg_overflow_t_f"]
        self.root.stats["avg_overflow_t_f"] = (dur / (c + 1.0)) + (c * oa / (c + 1.0))
        self.root.stats["overflow_f"] += 1
        self.root.stats["longest_overflow"] = max(self.root.stats["longest_overflow"], dur)

    def _set_children(self, cs):
        self.first_child = 0

        if 0 == len(cs):
            return

        parent_pool = self.root.node_parent_pool
        pred = None
        for c in cs:
            parent_pool[c.index] = self.index
            if pred is not None:
                pred.next_sibling = c.index
                pred._save_back()
            if 0 == self.first_child:
                self.first_child = c.index
            pred = c
        pred.next_sibling = 0
        pred._save_back()
        self._save_back()

    def _insert_child(self, c):
        self.root.node_parent_pool[c.index] = self.index
        c.next_sibling = self.first_child
        self.first_child = c.index
        c._save_back()
        self._save_back()

    def children(self):
        if 0 == self.first_child:
            return

        idx = self.index
        fc = self.first_child
        ns = self.next_sibling
        r = self.rect

        try:
            self._become(self.first_child)
            while True:
                yield self
                if 0 == self.next_sibling:
                    break
                else:
                    self._become(self.next_sibling)
        finally:
            # Go back to becoming the same node we were, even if the
            # caller stops iterating early (break) or raises.
            self.index = idx
            self.first_child = fc
            self.next_sibling = ns
            self.rect = r


def avg_diagonals(node, onodes, memo_tab):
    nidx = node.index
    sv = 0.0
    diag = 0.0
    for onode in onodes:
        k1 = (nidx, onode.index)
        k2 = (onode.index, nidx)
        if k1 in memo_tab:
            diag = memo_tab[k1]
        elif k2 in memo_tab:
            diag = memo_tab[k2]
        else:
            diag = node.rect.union(onode.rect).diagonal()
            memo_tab[k1] = diag

        sv += diag

    return sv / len(onodes)


def silhouette_w(node, cluster, next_closest_cluster, memo):
    ndist = avg_diagonals(node, cluster, memo)
    sdist = avg_diagonals(node, next_closest_cluster, memo)
    return (sdist - ndist) / max(sdist, ndist)


def silhouette_coeff(clustering, memo_tab):
    # special case for a clustering of 1.0
    if len(clustering) == 1:
        return 1.0

    coeffs = []
    for cluster in clustering:
        others = [c for c in clustering if c is not cluster]
        others_cntr = [center_of_gravity(c) for c in others]
        ws = [
            silhouette_w(node, cluster, others[closest(others_cntr, node)], memo_tab)
            for node in cluster
        ]
        cluster_coeff = sum(ws) / len(ws)
        coeffs.append(cluster_coeff)
    return sum(coeffs) / len(coeffs)


def center_of_gravity(nodes):
    totarea = 0.0
    xs, ys = 0.0, 0.0
    cxs, cys, count = 0.0, 0.0, 0
    for n in nodes:
        if n.rect is not NullRect:
            x, y, w, h = n.rect.extent()
            a = w * h
            cx, cy = x + (0.5 * w), y + (0.5 * h)
            xs = xs + (a * cx)
            ys = ys + (a * cy)
            cxs = cxs + cx
            cys = cys + cy
            totarea = totarea + a
            count += 1
    if count == 0:
        # No non-null rects at all (e.g. every node is NullRect) -- there's
        # no meaningful centroid, so fall back to the origin.
        return 0.0, 0.0
    if totarea == 0.0:
        # All rects in this cluster are degenerate (zero width and/or
        # height, e.g. points) -- fall back to an unweighted centroid
        # instead of dividing by zero.
        return (cxs / count), (cys / count)
    return (xs / totarea), (ys / totarea)


def closest(centroids, node):
    x, y = center_of_gravity([node])
    dist = -1
    ridx = -1

    for i, (xx, yy) in enumerate(centroids):
        dsq = ((xx - x) ** 2) + ((yy - y) ** 2)
        if -1 == dist or dsq < dist:
            dist = dsq
            ridx = i
    return ridx


def k_means_cluster(root, k, nodes):
    t = time.perf_counter()
    if len(nodes) <= k:
        return [[n] for n in nodes]

    ns = list(nodes)
    root.stats["count_kmeans_iter_f"] += 1

    # Initialize: take n random nodes.
    random.shuffle(ns)

    cluster_centers = [center_of_gravity([n]) for n in ns[:k]]

    # Loop until stable:
    while True:
        root.stats["sum_kmeans_iter_f"] += 1
        clusters = [[] for c in cluster_centers]

        for n in ns:
            idx = closest(cluster_centers, n)
            clusters[idx].append(n)

        # Two initial centers can end up close enough that one never becomes
        # the nearest center for any node, leaving it with no members. Drop
        # those empty clusters rather than keeping a hollow entry around --
        # this yields fewer than `k` clusters, which is fine since callers
        # only rely on there being at least one.
        clusters = [c for c in clusters if len(c) > 0]

        new_cluster_centers = [center_of_gravity(c) for c in clusters]
        if new_cluster_centers == cluster_centers:
            root.stats["avg_kmeans_iter_f"] = float(
                root.stats["sum_kmeans_iter_f"] / root.stats["count_kmeans_iter_f"]
            )
            root.stats["longest_kmeans"] = max(
                root.stats["longest_kmeans"], (time.perf_counter() - t)
            )
            return clusters
        else:
            cluster_centers = new_cluster_centers
