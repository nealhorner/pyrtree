import array
import collections
import math
import random
import unittest as ut

from pyrtree import Rect, RTree
from pyrtree.rect import NullRect
from pyrtree.rtree import center_of_gravity, closest, k_means_cluster, silhouette_coeff

from .testutil import take


def rr():
    return random.uniform(0.0, 10.0)


class TstO:
    """Dummy test object to store in r-trees."""

    def __init__(self, r):
        self.rect = r

    def walk(self, pred):
        if pred(self):
            yield self


class RectangleGen:
    """Generate random rectangles w/ various properties."""

    def rect(self, size=10.0):
        x, y, w, h = rr(), rr(), random.uniform(0.0, size), random.uniform(0.0, size)
        r = Rect(x, y, x + w, y + h)
        assert not r.swapped_x
        assert not r.swapped_y
        return r

    def intersectingWith(self, ra):
        rb_x = random.uniform(ra.x, ra.xx)
        rb_y = random.uniform(ra.y, ra.yy)
        return Rect(rb_x, rb_y, rb_x + rr(), rb_y + rr())

    def disjointWith(self, ra):
        ax, ay, aw, ah = ra.extent()
        w, h = rr(), rr()
        distsq = max(w * w + h * h, aw * aw + ah * ah)
        dist = 2.0 * math.sqrt(distsq) + random.uniform(0.1, 1.0)
        ang = random.uniform(0.0, 2.0 * math.pi)
        x = math.cos(ang) * dist
        y = math.sin(ang) * dist
        return Rect(ax + x, ay + y, ax + x + w, ay + y + h)

    def pointInside(self, r):
        return (random.uniform(r.x, r.xx), random.uniform(r.y, r.yy))

    def pointOutside(self, r):
        return self.pointInside(self.disjointWith(r))

    def rswap(self, a, b):
        rr = [a, b]
        random.shuffle(rr)
        return (rr[0], rr[1])

    def intersectingPair(self):
        ra = self.rect()
        rb = self.intersectingWith(ra)
        return self.rswap(ra, rb)

    def disjointPair(self):
        ra = self.rect()
        rb = self.disjointWith(ra)
        return self.rswap(ra, rb)


G = RectangleGen()


class RectangleTests(ut.TestCase):
    def testCons(self):
        r = Rect(0, 0, 10, 10)
        self.assertTrue(r is not None)
        self.assertTrue(r is not NullRect)

    def testIntersection(self):
        ra = Rect(0, 0, 10, 10)
        rb = Rect(5, 5, 15, 15)
        res = ra.intersect(rb)
        x, y, w, h = res.extent()
        self.assertEqual(x, 5)
        self.assertEqual(y, 5)
        self.assertEqual(w, 5)
        self.assertEqual(h, 5)
        self.assertEqual(res.area(), 25)

        rc = Rect(0, 0, 10, 10)
        rd = Rect(11, 11, 21, 21)
        res2 = rc.intersect(rd)
        self.assertEqual(res2.area(), 0)
        self.assertTrue(res2 is NullRect)

        for _ in range(1000):
            a, b = G.intersectingPair()
            self.assertTrue(a.intersect(b).area() > 0.0)
            c, d = G.disjointPair()
            self.assertEqual(c.intersect(d).area(), 0)

        self.assertTrue(ra.intersect(NullRect) is NullRect)
        self.assertTrue(NullRect.intersect(ra) is NullRect)

    def testUnion(self):
        ra = Rect(0, 0, 10, 10)
        rb = Rect(-10, -10, 1, 1)
        x, y, w, h = ra.union(rb).extent()
        self.assertEqual(x, -10)
        self.assertEqual(y, -10)
        self.assertEqual(w, 20)
        self.assertEqual(h, 20)

        for i in range(1000):
            a, b = G.rect(), G.rect()
            u = a.union(b)
            self.assertTrue(a.intersect(u).area() > 0)
            self.assertTrue(u.intersect(a).area() > 0)
            self.assertTrue(b.intersect(u).area() > 0)
            self.assertTrue(u.intersect(b).area() > 0)
            self.assertTrue(
                u.area() >= (max(a.area(), b.area())),
                f"union area (iter {i}) fail {u.area()} >= {max(a.area(), b.area())}",
            )

            c, d = G.disjointPair()
            u2 = c.union(d)
            self.assertTrue(c.intersect(u2).area() > 0)
            self.assertTrue(u2.intersect(c).area() > 0)
            self.assertTrue(d.intersect(u2).area() > 0)
            self.assertTrue(u2.intersect(d).area() > 0)
            self.assertTrue(u2.area() > c.area())
            self.assertTrue(u2.area() > d.area())
            self.assertTrue(u2.area() >= (c.area() + d.area()))

    def testContainPoint(self):
        rs = take(100, G.rect)
        for r in rs:
            self.assertTrue(r.does_containpoint(G.pointInside(r)))
            self.assertFalse(r.does_containpoint(G.pointOutside(r)))

    def testContainRects(self):
        for r in take(1000, G.rect):
            self.assertTrue(r.does_contain(r))
            ix = r.intersect(G.intersectingWith(r))

            self.assertTrue(r.does_contain(ix))
            out = G.disjointWith(r)
            self.assertFalse(r.does_contain(out))

    def testSwappedConstruction(self):
        r = Rect(10, 10, 0, 0)
        self.assertTrue(r.swapped_x)
        self.assertTrue(r.swapped_y)
        self.assertEqual(r.coords(), (0, 0, 10, 10))

        r2 = Rect(0, 0, 10, 10)
        self.assertFalse(r2.swapped_x)
        self.assertFalse(r2.swapped_y)

    def testGrow(self):
        r = Rect(0, 0, 10, 10).grow(4)
        self.assertEqual(r.coords(), (-2, -2, 12, 12))

    def testUnionPoint(self):
        r = Rect(0, 0, 10, 10)
        u = r.union_point((15, -5))
        self.assertTrue(u.does_contain(r))
        self.assertTrue(u.does_containpoint((15, -5)))
        self.assertEqual(u.coords(), (0, -5, 15, 10))

    def testDiagonal(self):
        r = Rect(0, 0, 3, 4)
        self.assertEqual(r.diagonal_sq(), 25)
        self.assertEqual(r.diagonal(), 5)
        self.assertEqual(NullRect.diagonal_sq(), 0)
        self.assertEqual(NullRect.diagonal(), 0)

    def testOverlap(self):
        ra = Rect(0, 0, 10, 10)
        rb = Rect(5, 5, 15, 15)
        self.assertEqual(ra.overlap(rb), ra.intersect(rb).area())
        self.assertEqual(ra.overlap(rb), 25)

    def testWriteRawCoords(self):
        r = Rect(1, 2, 8, 9)
        buf = array.array("d", [0, 0, 0, 0])
        r.write_raw_coords(buf, 0)
        self.assertEqual(list(buf), [1, 2, 8, 9])

        # write_raw_coords round-trips the original (possibly swapped)
        # constructor args -- that's how the swap flags get persisted
        # without extra storage (see class docstring).
        swapped = Rect(8, 9, 1, 2)
        buf2 = array.array("d", [0, 0, 0, 0])
        swapped.write_raw_coords(buf2, 0)
        self.assertEqual(list(buf2), [8, 9, 1, 2])

    def testNullRectUnion(self):
        r = Rect(0, 0, 10, 10)
        self.assertEqual(r.union(NullRect).coords(), r.coords())
        self.assertEqual(NullRect.union(r).coords(), r.coords())
        self.assertEqual(NullRect.area(), 0)


class RTreeTest(ut.TestCase):
    def testCons(self):
        RTree()

    def testEmptyTree(self):
        tree = RTree()
        self.assertEqual([r for r in tree.query_point((5, 5)) if r.is_leaf()], [])
        self.assertEqual([r for r in tree.query_rect(Rect(0, 0, 10, 10)) if r.is_leaf()], [])
        self.assertEqual([r for r in tree.walk(lambda x, y: True) if r.is_leaf()], [])

    def invariants(self, tree):
        self.assertEqual(tree.cursor.index, 0)
        self._invariants(tree.cursor, {})

    def _invariants(self, node, seen):
        idx = node.index

        self.assertTrue(idx not in seen)

        seen[idx] = True

        if node.holds_leaves():
            self.assertTrue(node.nchildren() == 0 or node.get_first_child().is_leaf())
            for c in node.children():
                self.assertTrue(c.is_leaf())
                self.assertTrue(isinstance(c.leaf_obj(), TstO))
        else:
            for c in node.children():
                self.assertTrue(not c.is_leaf())
        self.assertEqual(idx, node.index)

        r = Rect(node.rect.x, node.rect.y, node.rect.xx, node.rect.yy)
        for c in node.children():
            assert r.does_contain(c.rect)

        self.assertEqual(idx, node.index)

        for c in node.children():
            if not c.is_leaf():
                self._invariants(c, seen)

        self.assertEqual(idx, node.index)

    def testContainer(self):
        """Test container-like behaviour."""
        xs = [TstO(r) for r in take(100, G.rect, 0.1)]
        tree = RTree()
        for x in xs:
            tree.insert(x, x.rect)
            self.invariants(tree)

        ws = [x.leaf_obj() for x in tree.walk(lambda x, y: True) if x.is_leaf()]
        self.invariants(tree)
        rrs = collections.defaultdict(int)

        for w in ws:
            rrs[w] = rrs[w] + 1

        for x in xs:
            self.assertEqual(rrs[x], 1)

    def testDegenerateContainer(self):
        """Tests that an r-tree still works like a container even with highly overlapping rects."""
        xs = [TstO(r) for r in take(1000, G.rect, 20.0)]
        tree = RTree()
        for x in xs:
            tree.insert(x, x.rect)
            self.invariants(tree)

        ws = [x.leaf_obj() for x in tree.walk(lambda x, y: True) if x.is_leaf()]
        for x in xs:
            self.assertTrue(x in ws)

    def testInsertSame(self):
        tree = RTree()
        rect = G.rect()
        xs = [TstO(rect) for i in range(11)]
        for x in xs:
            tree.insert(x, x.rect)
            self.invariants(tree)

    def testOriginPointNotConfusedWithNullRect(self):
        """A genuine zero-area rect at the exact origin must round-trip as a
        real Rect, not silently collapse into the NullRect sentinel (which
        also stores raw coordinates (0,0,0,0))."""
        tree = RTree()
        origin = TstO(Rect(0, 0, 0, 0))
        tree.insert(origin, origin.rect)
        for i in range(1, 15):
            x = TstO(Rect(i, i, i + 1, i + 1))
            tree.insert(x, x.rect)
        self.invariants(tree)

        origin_leaf_rects = [
            n.rect for n in tree.walk(lambda x, y: True) if n.is_leaf() and n.leaf_obj() is origin
        ]
        self.assertEqual(len(origin_leaf_rects), 1)
        self.assertTrue(origin_leaf_rects[0] is not NullRect)

        # The origin point must widen the tree's bounding box, not get
        # dropped from it as if it were absent (NullRect).
        self.assertTrue(tree.cursor.rect.does_containpoint((0, 0)))

    def testPointQuery(self):
        xs = [TstO(r) for r in take(1000, G.rect, 0.01)]
        tree = RTree()
        for x in xs:
            tree.insert(x, x.rect)
            self.invariants(tree)

        for x in xs:
            qp = G.pointInside(x.rect)
            self.assertTrue(x.rect.does_containpoint(qp))
            op = G.pointOutside(x.rect)
            rs = list([r.leaf_obj() for r in tree.query_point(qp)])
            self.assertTrue(x in rs, f"Not in results of len {len(rs)} :(")
            rrs = list([r.leaf_obj() for r in tree.query_point(op)])
            self.assertFalse(x in rrs)

    def testRectQuery(self):
        xs = [TstO(r) for r in take(1000, G.rect, 0.01)]
        rt = RTree()
        for x in xs:
            rt.insert(x, x.rect)
            self.invariants(rt)

        for x in xs:
            qrect = G.intersectingWith(x.rect)
            orect = G.disjointWith(x.rect)
            self.assertTrue(qrect.does_intersect(x.rect))
            p = G.pointInside(x.rect)
            res = list([ro.leaf_obj() for ro in rt.query_point(p)])
            self.invariants(rt)
            self.assertTrue(x in res)
            res2 = list([r.leaf_obj() for r in rt.query_rect(qrect)])
            self.assertTrue(x in res2)
            rres = list([r.leaf_obj() for r in rt.query_rect(orect)])
            self.assertFalse(x in rres)

    def testAbandonedWalkDoesNotCorruptTree(self):
        """Partially consuming walk()/query_point()/query_rect() must not
        leave the tree's root cursor stuck mid-traversal.

        Filtering for is_leaf() forces each generator to recurse past the
        root and down into the tree (the root itself is never a leaf, and
        always trivially satisfies point/rect containment via the bounding
        box, so an unfiltered next() would stop before any recursion and
        not exercise the bug at all) before it gets abandoned without being
        exhausted.
        """
        xs = [TstO(r) for r in take(20, G.rect, 0.01)]
        tree = RTree()
        for x in xs:
            tree.insert(x, x.rect)
            self.invariants(tree)

        next(r for r in tree.walk(lambda x, y: True) if r.is_leaf())
        p = G.pointInside(xs[0].rect)
        next(r for r in tree.query_point(p) if r.is_leaf())
        qrect = G.intersectingWith(xs[0].rect)
        next(r for r in tree.query_rect(qrect) if r.is_leaf())

        # A subsequent insert must still succeed.
        extra = TstO(G.rect())
        tree.insert(extra, extra.rect)
        self.invariants(tree)

    def testDelete(self):
        xs = [TstO(r) for r in take(200, G.rect, 0.1)]
        tree = RTree()
        for x in xs:
            tree.insert(x, x.rect)
        self.invariants(tree)

        random.shuffle(xs)
        to_remove, to_keep = xs[:100], xs[100:]

        for x in to_remove:
            self.assertTrue(tree.delete(x, x.rect))
        self.invariants(tree)

        remaining = {r.leaf_obj() for r in tree.walk(lambda x, y: True) if r.is_leaf()}
        self.assertEqual(remaining, set(to_keep))

        for x in to_remove:
            qp = G.pointInside(x.rect)
            rs = [r.leaf_obj() for r in tree.query_point(qp)]
            self.assertFalse(x in rs)

        for x in to_keep:
            qp = G.pointInside(x.rect)
            rs = [r.leaf_obj() for r in tree.query_point(qp)]
            self.assertTrue(x in rs)

    def testDeleteMissingReturnsFalse(self):
        tree = RTree()
        present = TstO(Rect(0, 0, 1, 1))
        tree.insert(present, present.rect)

        absent = TstO(Rect(5, 5, 6, 6))
        self.assertFalse(tree.delete(absent, absent.rect))

        # Right object, wrong rect -- the rect is used to descend, so a
        # mismatched rect must not find the leaf either.
        self.assertFalse(tree.delete(present, Rect(5, 5, 6, 6)))

        self.assertTrue(tree.delete(present, present.rect))
        # A second delete of the same (now-removed) item fails.
        self.assertFalse(tree.delete(present, present.rect))

    def testDeleteThenInsertStillWorks(self):
        """Deleting must not corrupt the tree's ability to keep growing
        (exercises rebalancing after nodes have been unlinked)."""
        tree = RTree()
        xs = [TstO(r) for r in take(50, G.rect, 0.1)]
        for x in xs:
            tree.insert(x, x.rect)

        for x in xs[:25]:
            self.assertTrue(tree.delete(x, x.rect))
        self.invariants(tree)

        more = [TstO(r) for r in take(50, G.rect, 0.1)]
        for x in more:
            tree.insert(x, x.rect)
            self.invariants(tree)

        expected = set(xs[25:]) | set(more)
        actual = {r.leaf_obj() for r in tree.walk(lambda x, y: True) if r.is_leaf()}
        self.assertEqual(actual, expected)


class _FakeNode:
    """Minimal stand-in for a _NodeCursor: the clustering functions below
    only ever touch .index and .rect."""

    def __init__(self, index, rect):
        self.index = index
        self.rect = rect


class ClusteringTests(ut.TestCase):
    """The k-means clustering used by RTree._balance() has no coverage
    from the RTree insert/query tests, since it's only exercised
    indirectly once a node overflows. Test it directly instead."""

    def testCenterOfGravity(self):
        node = _FakeNode(0, Rect(0, 0, 2, 2))
        self.assertEqual(center_of_gravity([node]), (1.0, 1.0))

    def testClosest(self):
        centroids = [(0.0, 0.0), (100.0, 100.0)]
        near_first = _FakeNode(0, Rect(1, 1, 2, 2))
        near_second = _FakeNode(1, Rect(99, 99, 101, 101))
        self.assertEqual(closest(centroids, near_first), 0)
        self.assertEqual(closest(centroids, near_second), 1)

    def testKMeansClusterSeparatesDistinctGroups(self):
        root = RTree()
        near_origin = [
            _FakeNode(i, Rect(i * 0.1, i * 0.1, i * 0.1 + 1, i * 0.1 + 1)) for i in range(4)
        ]
        far_away = [
            _FakeNode(
                100 + i,
                Rect(100 + i * 0.1, 100 + i * 0.1, 101 + i * 0.1, 101 + i * 0.1),
            )
            for i in range(4)
        ]
        nodes = near_origin + far_away

        clusters = k_means_cluster(root, 2, nodes)

        # k_means_cluster drops empty groups during convergence, so it can
        # legitimately return fewer than k clusters -- don't assert an exact
        # count. What matters is that well-separated points never end up
        # mixed together, which is checked below.
        self.assertLessEqual(len(clusters), 2)
        all_indices = sorted(n.index for c in clusters for n in c)
        self.assertEqual(all_indices, sorted(n.index for n in nodes))

        origin_indices = {n.index for n in near_origin}
        far_indices = {n.index for n in far_away}
        for cluster in clusters:
            cluster_indices = {n.index for n in cluster}
            self.assertTrue(
                cluster_indices <= origin_indices or cluster_indices <= far_indices,
                f"cluster {cluster_indices!r} mixed the two separated groups",
            )

    def testSilhouetteCoeffHighForWellSeparatedClusters(self):
        near_origin = [
            _FakeNode(i, Rect(i * 0.1, i * 0.1, i * 0.1 + 1, i * 0.1 + 1)) for i in range(4)
        ]
        far_away = [
            _FakeNode(
                100 + i,
                Rect(100 + i * 0.1, 100 + i * 0.1, 101 + i * 0.1, 101 + i * 0.1),
            )
            for i in range(4)
        ]
        score = silhouette_coeff([near_origin, far_away], {})
        self.assertTrue(score > 0.8, f"expected a high score, got {score}")

    def testSilhouetteCoeffSingleClusterIsOne(self):
        node = _FakeNode(0, Rect(0, 0, 1, 1))
        self.assertEqual(silhouette_coeff([[node]], {}), 1.0)


if __name__ == "__main__":
    ut.main()
