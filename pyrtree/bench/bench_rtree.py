import gc

# TODO: make these command-line params.
import os
import time

from pyrtree.rtree import RTree
from pyrtree.tests.test_rtree import RectangleGen, TstO

ITER = 1000000  # one meeelion
if "TEST_ITER" in os.environ:
    ITER = int(os.getenv("TEST_ITER"))
INTERVAL = 1000  # log at every 1k
if "TEST_INTERVAL" in os.environ:
    INTERVAL = int(os.getenv("TEST_INTERVAL"))


if __name__ == "__main__":
    gc.disable()  # FFFFUUUUUUUUUUU
    G = RectangleGen()
    rt = RTree()
    start = time.perf_counter()
    interval_start = time.perf_counter()
    for v in range(ITER):
        if 0 == (v % INTERVAL):
            # interval time taken, total time taken, # rects, cur max depth
            t = time.perf_counter()

            dt = t - interval_start
            print(f"{v:d},itime_t,{dt:f}")
            print(f"{v:d},avg_insert_t,{dt / float(INTERVAL):f}")
            for k, val in rt.stats.items():
                print(f"{v:d},{k},{val:f}")
            for k in rt.stats.keys():
                if k.endswith("_f"):
                    rt.stats[k] = 0.0

            # print("%d,%s,%d" % (v, "max_depth", rt.node.max_depth()))
            # print("%d,%s,%d" % (v, "mean_depth", rt.node.mean_depth()))

            interval_start = time.perf_counter()
        o = TstO(G.rect(0.000001))
        rt.insert(v, o.rect)

    # Done.
