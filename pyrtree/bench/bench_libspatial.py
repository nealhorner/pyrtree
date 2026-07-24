# Like bench_rtree but uses the libspatialindex c library. For comparison!
# http://pypi.python.org/pypi/Rtree

import time

from rtree import Rtree

from pyrtree.bench.bench_rtree import GROWTH, ITER, ExponentialLogSchedule
from pyrtree.tests.test_rtree import RectangleGen

if __name__ == "__main__":
    G = RectangleGen()
    idx = Rtree()  # this is a libspatialindex one.
    schedule = ExponentialLogSchedule(GROWTH)
    interval_start = time.perf_counter()
    last_v = 0
    for v in range(ITER):
        if schedule.hit(v):
            # interval time taken, total time taken, # rects, cur max depth
            t = time.perf_counter()

            dt = t - interval_start
            count = v - last_v
            print(f"{v:d},itime_t,{dt:f}")
            if count > 0:
                print(f"{v:d},avg_insert_t,{dt / float(count):f}")

            interval_start = time.perf_counter()
            last_v = v
        rect = G.rect(0.000001)
        idx.add(v, rect.coords())
