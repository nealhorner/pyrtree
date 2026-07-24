# Like bench_rtree but uses the libspatialindex c library. For comparison!
# http://pypi.python.org/pypi/Rtree

import time

from rtree import Rtree

from pyrtree.bench.bench_rtree import INTERVAL, ITER
from pyrtree.tests.test_rtree import RectangleGen

if __name__ == "__main__":
    G = RectangleGen()
    idx = Rtree()  # this is a libspatialindex one.
    start = time.perf_counter()
    interval_start = time.perf_counter()
    for v in range(ITER):
        if 0 == (v % INTERVAL):
            # interval time taken, total time taken, # rects, cur max depth
            t = time.perf_counter()

            dt = t - interval_start
            print(f"{v:d},itime_t,{dt:f}")
            print(f"{v:d},avg_insert_t,{dt / float(INTERVAL):f}")
            # print("%d,%s,%d" % (v, "max_depth", rt.node.max_depth()))
            # print("%d,%s,%d" % (v, "mean_depth", rt.node.mean_depth()))

            interval_start = time.perf_counter()
        rect = G.rect(0.000001)
        idx.add(v, rect.coords())
