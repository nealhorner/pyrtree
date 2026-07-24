import gc
import math

# TODO: make these command-line params.
import os
import time

from pyrtree.rtree import RTree
from pyrtree.tests.test_rtree import RectangleGen, TstO

ITER = 1000000  # one meeelion
if "TEST_ITER" in os.environ:
    ITER = int(os.getenv("TEST_ITER"))
GROWTH = 2.0  # log points grow by this factor: 0, 1, 2, 4, 8, ...
if "TEST_GROWTH" in os.environ:
    GROWTH = float(os.getenv("TEST_GROWTH"))


class ExponentialLogSchedule:
    """True at v = 0, 1, 2, 4, 8, ... (each point `growth`x the last)."""

    def __init__(self, growth):
        if not math.isfinite(growth) or growth <= 1:
            raise ValueError("growth must be finite and greater than 1")
        self.growth = growth
        self.next_log = 0

    def hit(self, v):
        if v != self.next_log:
            return False
        self.next_log = (
            1 if self.next_log == 0 else max(self.next_log + 1, int(self.next_log * self.growth))
        )
        return True


if __name__ == "__main__":
    gc.disable()  # FFFFUUUUUUUUUUU
    G = RectangleGen()
    rt = RTree()
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
            for k, val in rt.stats.items():
                print(f"{v:d},{k},{val:f}")
            for k in rt.stats.keys():
                if k.endswith("_f"):
                    rt.stats[k] = 0.0

            interval_start = time.perf_counter()
            last_v = v
        o = TstO(G.rect(0.000001))
        rt.insert(v, o.rect)

    # Done.
