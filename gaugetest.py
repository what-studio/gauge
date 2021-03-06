# -*- coding: utf-8 -*-
from contextlib import contextmanager
import gc
import math
import operator
import pickle
import random
from random import Random
import time

import pytest
from pytest import approx

import gauge
from gauge import Gauge, Momentum
from gauge.constants import ADD, CLAMP, inf, NONE, OK, ONCE, REMOVE
from gauge.deterministic import (
    Boundary, Determination, Horizon, Line, Ray, Segment)


PRECISION = 8
TIME, VALUE = 0, 1


class FakeGauge(Gauge):

    def __init__(self, determination):
        super(FakeGauge, self).__init__(0, 0, 0, 0)
        self._determination = Determination.__new__(Determination)
        self._determination.extend(determination)

    @property
    def determination(self):
        return self._determination


def round_(x):
    return round(x, PRECISION)


@contextmanager
def t(timestamp):
    gauge.core.now = lambda: float(timestamp)
    try:
        yield
    finally:
        gauge.core.now = time.time


def round_determination(determination, precision=0):
    return [(round(time, precision), round(value, precision))
            for time, value in determination]


def is_gauge(x):
    """Whether the value is an instance of :class:`Gauge`."""
    return isinstance(x, Gauge)


def shift_gauge(gauge, delta=0):
    """Adds the given delta to a gauge."""
    if gauge.max_gauge is None:
        max_ = gauge.max_value + delta
    else:
        max_ = shift_gauge(gauge.max_gauge, delta)
    if gauge.min_gauge is None:
        min_ = gauge.min_value + delta
    else:
        min_ = shift_gauge(gauge.min_gauge, delta)
    g = Gauge(gauge.base[VALUE] + delta, max_, min_, gauge.base[TIME])
    for momentum in gauge.momenta:
        g.add_momentum(momentum)
    return g


def test_momenta_in_range():
    g = Gauge(12, 100, at=0)
    g.add_momentum(+1, since=1, until=6)
    g.add_momentum(-1, since=3, until=8)
    assert g.determination == [
        (0, 12), (1, 12), (3, 14), (6, 14), (8, 12)]


def test_over_max():
    g = Gauge(8, 10, at=0)
    g.add_momentum(+1, since=0, until=4)
    assert g.determination == [(0, 8), (2, 10), (4, 10)]
    g = Gauge(12, 10, at=0)
    g.add_momentum(-1, since=0, until=4)
    assert g.determination == [(0, 12), (2, 10), (4, 8)]
    g = Gauge(12, 10, at=0)
    g.add_momentum(+1, since=0, until=4)
    g.add_momentum(-2, since=0, until=4)
    assert g.determination == [(0, 12), (1, 10), (4, 7)]
    g = Gauge(12, 10, at=0)
    g.add_momentum(+1, since=1, until=6)
    g.add_momentum(-1, since=3, until=8)
    g.add_momentum(+1, since=10, until=14)
    g.add_momentum(-1, since=13, until=16)
    assert g.determination == [
        (0, 12), (1, 12), (3, 12), (5, 10), (6, 10), (8, 8),
        (10, 8), (12, 10), (13, 10), (14, 10), (16, 8)]


def test_under_min():
    g = Gauge(2, 10, at=0)
    g.add_momentum(-1, since=0, until=4)
    assert g.determination == [(0, 2), (2, 0), (4, 0)]
    g = Gauge(-2, 10, at=0)
    g.add_momentum(+1, since=0, until=4)
    assert g.determination == [(0, -2), (2, 0), (4, 2)]
    g = Gauge(-2, 10, at=0)
    g.add_momentum(-1, since=0, until=4)
    g.add_momentum(+2, since=0, until=4)
    assert g.determination == [(0, -2), (1, 0), (4, 3)]
    g = Gauge(-2, 10, at=0)
    g.add_momentum(-1, since=1, until=6)
    g.add_momentum(+1, since=3, until=8)
    g.add_momentum(-1, since=10, until=14)
    g.add_momentum(+1, since=13, until=16)
    assert g.determination == [
        (0, -2), (1, -2), (3, -2), (5, 0), (6, 0), (8, 2),
        (10, 2), (12, 0), (13, 0), (14, 0), (16, 2)]


def test_permanent():
    g = Gauge(10, 10, at=0)
    g.add_momentum(-1)
    assert g.determination == [(0, 10), (10, 0)]
    g = Gauge(0, 10, at=0)
    g.add_momentum(+1)
    assert g.determination == [(0, 0), (10, 10)]
    g = Gauge(12, 10, at=0)
    g.add_momentum(-1)
    assert g.determination == [(0, 12), (2, 10), (12, 0)]
    g = Gauge(5, 10, at=0)
    g.add_momentum(+1, since=3)
    assert g.determination == [(0, 5), (3, 5), (8, 10)]
    g = Gauge(5, 10, at=0)
    g.add_momentum(+1, until=8)
    assert g.determination == [(0, 5), (5, 10), (8, 10)]


def test_life():
    with t(0):
        life = Gauge(100, 100)
        life.add_momentum(-1)
        assert life.get() == 100
    with t(1):
        assert life.get() == 99
    with t(2):
        assert life.get() == 98
    with t(10):
        assert life.get() == 90
        life.incr(1)
        assert life.get() == 91
    with t(11):
        assert life.get() == 90


def test_no_momentum():
    g = Gauge(1, 10, at=0)
    assert g.determination == [(0, 1)]
    assert g.get() == 1


def test_ok_outbound():
    g = Gauge(1, 10)
    with pytest.raises(ValueError):
        g.set(11)
    with pytest.raises(ValueError):
        g.incr(100)
    with pytest.raises(ValueError):
        g.decr(100)
    g.set(10)
    assert g.get() == 10
    g.set(11, outbound=OK)
    assert g.get() == 11


def test_once_outbound():
    g = Gauge(1, 10)
    assert g.incr(5, outbound=ONCE) == 6
    assert g.incr(5, outbound=ONCE) == 11
    with pytest.raises(ValueError):
        g.incr(1, outbound=ONCE)


def test_clamp_outbound():
    g = Gauge(1, 10)
    g.set(11, outbound=CLAMP)
    assert g.get() == 10
    g.incr(100, outbound=CLAMP)
    assert g.get() == 10
    g.decr(100, outbound=CLAMP)
    assert g.get() == 0
    g.incr(3, outbound=CLAMP)
    assert g.get() == 3
    g.decr(1, outbound=CLAMP)
    assert g.get() == 2
    g.set(100, outbound=OK)
    g.incr(3, outbound=CLAMP)
    assert g.get() == 100
    g.decr(3, outbound=CLAMP)
    assert g.get() == 97
    g.set(98, outbound=CLAMP)
    assert g.get() == 97
    g.set(97, outbound=CLAMP)
    assert g.get() == 97
    g.set(96, outbound=CLAMP)
    assert g.get() == 96


def test_set_min_max():
    # without momentum
    g = Gauge(5, 10)
    assert g.get_max() == 10
    assert g.get_min() == 0
    assert g.get() == 5
    g.set_range(max=100, min=10)
    assert g.get_max() == 100
    assert g.get_min() == 10
    assert g.get() == 10
    g.set_min(10)
    assert g.get() == 10
    g.set_min(5)
    assert g.get() == 10
    g.set_range(max=5, min=0)
    assert g.get_max() == 5
    assert g.get_min() == 0
    assert g.get() == 5
    # with momentum
    g = Gauge(5, 10, at=0)
    g.add_momentum(+1)
    assert g.determination == [(0, 5), (5, 10)]
    g.set_max(50, at=0)
    assert g.determination == [(0, 5), (45, 50)]
    g.set_min(40, at=0)
    assert g.determination == [(0, 40), (10, 50)]


def test_pickle():
    g = Gauge(0, 10, at=0)
    r = Random(17171771)
    for x in range(10000):
        since = r.randrange(1000)
        until = since + 1 + r.randrange(1000)
        g.add_momentum(r.uniform(-10, +10), since=since, until=until)
    data = pickle.dumps(g)
    g2 = pickle.loads(data)
    assert g.determination == g2.determination


def test_make_momentum():
    g = Gauge(0, 10, at=0)
    m = g.add_momentum(+1)
    assert isinstance(m, Momentum)
    with pytest.raises(TypeError):
        g.add_momentum(m, since=1)
    with pytest.raises(TypeError):
        g.add_momentum(m, until=2)


def test_clear_momenta():
    g = Gauge(0, 10, at=0)
    g.add_momentum(+1)
    g.clear_momenta(at=5)
    assert g.get(5) == 5
    assert g.determination == [(5, 5)]
    # clear momenta when the value is out of the range
    g.add_momentum(+1)
    g.set(15, outbound=OK, at=10)
    g.clear_momenta(at=10)
    assert g.get(10) == 15
    assert g.determination == [(10, 15)]
    # rebase by Gauge.clear_momenta()
    g.clear_momenta(100)
    assert g.get() == 100


def test_when():
    g = Gauge(0, 10, at=0)
    assert g.when(0) == 0
    with pytest.raises(ValueError):
        g.when(10)
    g.add_momentum(+1)
    assert g.when(10) == 10
    g.add_momentum(+1, since=3, until=5)
    assert g.when(10) == 8
    g.add_momentum(-2, since=4, until=8)
    assert g.when(0) == 0
    assert g.when(1) == 1
    assert g.when(2) == 2
    assert g.when(3) == 3
    assert g.when(4) == 3.5
    assert g.when(5) == 4
    assert g.when(6) == 12
    assert g.when(7) == 13
    assert g.when(8) == 14
    assert g.when(9) == 15
    assert g.when(10) == 16
    with pytest.raises(ValueError):
        g.when(11)


def test_whenever():
    g = Gauge(0, 10, at=0)
    g.add_momentum(+1)
    g.add_momentum(-2, since=3, until=4)
    g.add_momentum(-2, since=5, until=6)
    g.add_momentum(-2, since=7, until=8)
    assert g.when(3) == 3
    assert g.when(3, after=1) == 5
    assert g.when(3, after=2) == 7
    assert g.when(3, after=3) == 9
    with pytest.raises(ValueError):
        g.when(3, after=4)
    whenever = g.whenever(3)
    assert list(whenever) == [3, 5, 7, 9]
    # inverse
    g = Gauge(10, 10, at=0)
    g.add_momentum(-1)
    g.add_momentum(+2, since=3, until=4)
    g.add_momentum(+2, since=5, until=6)
    g.add_momentum(+2, since=7, until=8)
    assert g.when(7) == 3
    assert g.when(7, after=1) == 5


def test_since_gte_until():
    g = Gauge(0, 10, at=0)
    with pytest.raises(ValueError):
        g.add_momentum(+1, since=1, until=1)
    with pytest.raises(ValueError):
        g.add_momentum(+1, since=2, until=1)


def test_repr():
    g = Gauge(0, 10, at=0)
    assert repr(g) == '<Gauge 0.00/10.00>'
    g.set_min(-10, at=0)
    assert repr(g) == '<Gauge 0.00 between -10.00~10.00>'
    g.set_max(Gauge(10, 10), at=0)
    assert repr(g) == '<Gauge 0.00 between -10.00~<Gauge 10.00/10.00>>'
    m = Momentum(+100, since=10, until=20)
    assert repr(m) == '<Momentum +100.00/s 10.00~20.00>'
    m = Momentum(+100, since=10)
    assert repr(m) == '<Momentum +100.00/s 10.00~>'
    m = Momentum(+100, until=20)
    assert repr(m) == '<Momentum +100.00/s ~20.00>'
    h = Horizon(10, 20, 30)
    assert repr(h) == '<Line[HORIZON] 30.00 for 10.00~20.00>'
    r = Ray(10, 20, 30, 40)
    assert repr(r) == '<Line[RAY] 30.00+40.00/s for 10.00~20.00>'


def test_case1():
    g = Gauge(0, 5, at=0)
    g.add_momentum(+1)
    g.add_momentum(-2, since=1, until=3)
    g.add_momentum(+1, since=5, until=7)
    assert g.determination == [
        (0, 0), (1, 1), (2, 0), (3, 0), (5, 2), (6.5, 5), (7, 5)]


def test_case2():
    g = Gauge(12, 10, at=0)
    g.add_momentum(+2, since=2, until=10)
    g.add_momentum(-1, since=4, until=8)
    assert g.determination == [
        (0, 12), (2, 12), (4, 12), (6, 10), (8, 10), (10, 10)]


def test_case3():
    g = Gauge(0, 10, at=0)
    assert g.get(0) == 0
    g.add_momentum(+1, since=0)
    assert g.get(10) == 10
    g.incr(3, outbound=OK, at=11)
    assert g.get(11) == 13
    g.add_momentum(-1, since=13)
    assert g.get(13) == 13
    assert g.get(14) == 12
    assert g.get(15) == 11
    assert g.get(16) == 10
    assert g.get(17) == 10


def test_case4():
    g = Gauge(0, 10, at=0)
    g.add_momentum(+1)
    g.add_momentum(+1)
    assert g.determination == [(0, 0), (5, 10)]


def test_case5():
    g = Gauge(1, 1, 0, at=0)
    for x in range(11):
        g.add_momentum(-0.1, since=x, until=x + 1)
    assert g.get(11) == 0  # adjusted by min=0


def test_case6():
    g = Gauge(1, 10, at=1417868986.94428)
    g.add_momentum(+0.167)
    g.add_momentum(-0.417, since=1417863954.884099)
    assert g.determination[-1][VALUE] == 0


def test_remove_momentum():
    g = Gauge(0, 10, at=0)
    m1 = g.add_momentum(+1)
    m2 = g.add_momentum(Momentum(+1))
    g.add_momentum(+2, since=10)
    g.add_momentum(-3, until=100)
    assert len(g.momenta) == 4
    assert g.remove_momentum(m2) == m2
    assert len(g.momenta) == 3
    assert m1 in g.momenta
    assert m2 in g.momenta
    assert g.remove_momentum(m2) == m2
    assert len(g.momenta) == 2
    assert m1 not in g.momenta
    assert m2 not in g.momenta
    with pytest.raises(ValueError):
        g.remove_momentum(+2)
    assert g.remove_momentum(+2, since=10) == (+2, 10, +inf)
    assert len(g.momenta) == 1
    assert g.remove_momentum(Momentum(-3, until=100)) == (-3, -inf, 100)
    assert not g.momenta


def test_remove_momentum_event_on_remove_momentum():
    g = Gauge(0, 10, at=0)
    g.add_momentum(+1)
    assert g.determination == [(0, 0), (10, 10)]
    g.remove_momentum(+1)
    g.add_momentum(+1)
    assert g.determination == [(0, 0), (10, 10)]
    g.remove_momentum(+1)
    g.add_momentum(+1)
    g.add_momentum(+1)
    assert g.determination == [(0, 0), (5, 10)]
    g.clear_momenta(at=0)
    g.add_momentum(+1)
    assert g.determination == [(0, 0), (10, 10)]


def test_momenta_order():
    g = Gauge(0, 50, at=0)
    g.add_momentum(+3, since=0, until=5)
    g.add_momentum(+2, since=1, until=4)
    g.add_momentum(+1, since=2, until=3)
    assert g.get(0) == 0
    assert g.get(1) == 3
    assert g.get(2) == 8
    assert g.get(3) == 14
    g.decr(1, at=3)
    assert g.get(3) == 13
    assert g.get(4) == 18
    assert g.get(5) == 21


def test_forget_past():
    g = Gauge(0, 50, at=0)
    g.add_momentum(+1, since=0, until=5)
    g.add_momentum(0, since=0)
    g.add_momentum(0, until=999)
    assert g.get(0) == 0
    assert g.get(1) == 1
    assert g.get(2) == 2
    assert g.get(3) == 3
    assert g.get(4) == 4
    assert g.get(5) == 5
    assert g.get(10) == 5
    assert g.get(20) == 5
    assert len(g.momenta) == 3
    g.forget_past(at=30)
    assert len(g.momenta) == 2


def test_forget_past_before_base_time():
    g = Gauge(0, 100, at=100)
    g.add_momentum(+1)
    assert g.get(100) == 0
    assert g.get(150) == 50
    assert g.get(200) == 100

    with pytest.raises(ValueError):
        g.forget_past(at=50)
    assert g.get(100) == 0
    assert g.get(150) == 50
    assert g.get(200) == 100

    g.forget_past(at=150)
    assert g.get(100) == 50
    assert g.get(150) == 50
    assert g.get(200) == 100

    with pytest.raises(ValueError):
        g.forget_past(0, at=100)
    assert g.get(100) == 50
    assert g.get(150) == 50
    assert g.get(200) == 100


def test_extensibility_of_make_momentum():
    class MyGauge(Gauge):
        def _make_momentum(self, *args):
            args = args[::-1]
            return super(MyGauge, self)._make_momentum(*args)
    g = MyGauge(0, 10, at=0)
    m = g.add_momentum(3, 2, 1)
    assert m == (1, 2, 3)


def test_just_one_momentum():
    def gen_gauge(since=None, until=None):
        g = Gauge(5, 10, at=0)
        g.add_momentum(+0.1, since, until)
        return g
    # None ~ None
    g = gen_gauge()
    assert g.determination == [(0, 5), (50, 10)]
    # 0 ~ None
    g = gen_gauge(since=0)
    assert g.determination == [(0, 5), (50, 10)]
    # None ~ 100
    g = gen_gauge(until=100)
    assert g.determination == [(0, 5), (50, 10), (100, 10)]
    # 0 ~ 100
    g = gen_gauge(since=0, until=100)
    assert g.determination == [(0, 5), (50, 10), (100, 10)]
    # -100 ~ 100
    g = gen_gauge(since=-100, until=100)
    assert g.determination == [(0, 5), (50, 10), (100, 10)]


def test_velocity():
    g = Gauge(0, 10, at=0)
    g.add_momentum(+1, since=2)
    g.add_momentum(+1, since=4, until=6)
    assert g.velocity(at=0) == 0
    assert g.velocity(at=2) == +1
    assert g.velocity(at=3) == +1
    assert g.velocity(at=4) == +2
    assert g.velocity(at=5) == +2
    assert g.velocity(at=6) == +1
    assert g.velocity(at=7) == +1
    assert g.velocity(at=8) == +1
    assert g.velocity(at=9) == +1
    assert g.velocity(at=10) == 0


def test_lines():
    horizon = Horizon(0, 10, 1234)
    assert horizon.get(0) == 1234
    assert horizon.get(10) == 1234
    assert horizon.guess(100) == 1234
    assert horizon.guess(-100) == 1234
    ray = Ray(0, 10, 0, velocity=+1)
    assert ray.get(0) == 0
    assert ray.get(5) == 5
    with pytest.raises(ValueError):
        ray.get(-1)
    with pytest.raises(ValueError):
        ray.get(11)
    assert ray.guess(-1) == 0
    assert ray.guess(11) == 10
    assert ray.intersect(Horizon(0, 10, 5)) == (5, 5)
    assert ray.intersect(Horizon(0, 10, 10)) == (10, 10)
    assert ray.intersect(Horizon(0, +inf, 5)) == (5, 5)
    with pytest.raises(ValueError):
        ray.intersect(Horizon(0, 10, 15))
    with pytest.raises(ValueError):
        ray.intersect(Horizon(6, 10, 5))
    with pytest.raises(ValueError):
        ray.intersect(Horizon(-inf, +inf, 5))
    ray = Ray(0, +inf, 0, velocity=+1)
    assert ray.get(100) == 100
    assert ray.get(100000) == 100000
    seg = Segment(0, 10, -50.05804016454045, 12.780503036230357)
    assert seg.get(10) == 12.780503036230357
    assert seg.guess(100) == 12.780503036230357
    assert seg.guess(-100) == -50.05804016454045


def test_boundary():
    # walk
    lines = [Horizon(0, 10, 0),
             Ray(10, 20, 0, velocity=+1),
             Ray(20, 30, 10, velocity=-1)]
    boundary = Boundary(lines)
    assert boundary.line is lines[0]
    boundary.walk()
    assert boundary.line is lines[1]
    boundary.walk()
    assert boundary.line is lines[2]
    with pytest.raises(StopIteration):
        boundary.walk()
    # cmp
    assert boundary.cmp(1, 2)
    assert not boundary.cmp(2, 1)
    assert boundary.cmp_eq(1, 2)
    assert boundary.cmp_eq(1, 1)
    assert not boundary.cmp_eq(2, 1)
    assert boundary.cmp_inv(2, 1)
    assert not boundary.cmp_inv(1, 2)
    assert not boundary.cmp_inv(1, 1)
    # best
    zero_line = Segment(0, 0, 0, 0)
    ceil = Boundary([zero_line], operator.lt)
    floor = Boundary([zero_line], operator.gt)
    assert ceil.best is min
    assert floor.best is max
    # repr
    assert repr(ceil) == ('<Boundary line={0}, cmp=<built-in function lt>>'
                          ''.format(zero_line))


@pytest.fixture
def zigzag():
    g = Gauge(1, Gauge(2, 3, 2, at=0), Gauge(1, 1, 0, at=0), at=0)
    for x in range(6):
        g.max_gauge.add_momentum(+1, since=x * 2, until=x * 2 + 1)
        g.max_gauge.add_momentum(-1, since=x * 2 + 1, until=x * 2 + 2)
        g.min_gauge.add_momentum(-1, since=x * 2, until=x * 2 + 1)
        g.min_gauge.add_momentum(+1, since=x * 2 + 1, until=x * 2 + 2)
    for x in range(3):
        t = sum(y * 2 for y in range(x + 1))
        g.add_momentum(+1, since=t, until=t + (x + 1))
        g.add_momentum(-1, since=t + (x + 1), until=t + 2 * (x + 1))
    return g


@pytest.fixture
def bidir():
    g = Gauge(5, Gauge(10, 10, at=0), Gauge(0, 10, at=0), at=0)
    g.add_momentum(+1, since=0, until=3)
    g.add_momentum(-1, since=3, until=6)
    g.add_momentum(+1, since=6, until=9)
    g.add_momentum(-1, since=9, until=12)
    g.max_gauge.add_momentum(-1, since=0, until=4)
    g.max_gauge.add_momentum(+1, since=6, until=7)
    g.min_gauge.add_momentum(+1, since=1, until=6)
    g.min_gauge.add_momentum(-1, since=6, until=8)
    return g


def test_hypergauge_case1():
    g = Gauge(12, 100, at=0)
    g.add_momentum(+1, since=1, until=6)
    g.add_momentum(-1, since=3, until=8)
    g.set_max(Gauge(15, 15, at=0), at=0)
    g.max_gauge.add_momentum(-1, until=5)
    assert g.determination == [
        (0, 12), (1, 12), (2, 13), (3, 12), (5, 10), (6, 10), (8, 8)]
    assert g.max_gauge.determination == [(0, 15), (5, 10)]


def test_hypergauge_case2():
    g = Gauge(12, 100, at=0)
    g.add_momentum(+1, since=1, until=6)
    g.add_momentum(-1, since=3, until=8)
    g.set_max(Gauge(15, 15, at=0), at=0)
    g.max_gauge.add_momentum(-1, until=4)
    g.max_gauge.add_momentum(+1, since=4, until=6)
    assert g.determination == [
        (0, 12), (1, 12), (2, 13), (3, 12), (4, 11), (6, 11), (8, 9)]


def test_hypergauge_case3():
    g = Gauge(12, 100, at=0)
    g.add_momentum(+1, since=1, until=6)
    g.add_momentum(-1, since=3, until=8)
    g.set_max(10, at=0)
    g.set(12, outbound=OK, at=0)
    assert g.determination == [
        (0, 12), (1, 12), (3, 12), (5, 10), (6, 10), (8, 8)]
    g.set_max(Gauge(10, 100, at=0), at=0)
    assert g.determination == [
        (0, 12), (1, 12), (3, 12), (5, 10), (6, 10), (8, 8)]


def test_hypergauge_case4():
    g = Gauge(12, 100, at=0)
    g.add_momentum(+1, since=1, until=6)
    g.add_momentum(-1, since=3, until=8)
    g.set_max(Gauge(15, 15, at=0), at=0)
    g.max_gauge.add_momentum(-1)
    assert g.determination == [
        (0, 12), (1, 12), (2, 13), (3, 12), (6, 9), (8, 7), (15, 0)]
    # bidirectional hyper-gauge
    g_max = Gauge(10, 10, at=0)
    g_max.add_momentum(-1, since=0, until=4)
    g_max.add_momentum(+1, since=6, until=7)
    g_min = Gauge(0, 10, at=0)
    g_min.add_momentum(+1, since=1, until=6)
    g_min.add_momentum(-1, since=6, until=8)
    g = Gauge(5, g_max, g_min, at=0)
    g.add_momentum(+1, since=0, until=3)
    g.add_momentum(-1, since=3, until=6)
    g.add_momentum(+1, since=6, until=9)
    g.add_momentum(-1, since=9, until=12)
    assert g.determination == [
        (0, 5), (2.5, 7.5), (3, 7), (4, 6), (5.5, 4.5), (6, 5), (8, 7),
        (9, 7), (12, 4)]
    g_min.incr(1, at=5)
    assert g.determination == [(5, 5), (6, 6), (7, 7), (9, 7), (12, 4)]


def test_hypergauge_zigzag1(zigzag):
    assert zigzag.determination == [
        (0, 1), (1, 2), (2, 1), (3.5, 2.5), (4, 2), (5.5, 0.5), (6, 1),
        (7.5, 2.5), (8, 2), (9, 3), (10, 2), (11.5, 0.5), (12, 1)]


def test_hypergauge_zigzag2():
    g = Gauge(2, Gauge(3, 5, 3, at=0), Gauge(2, 2, 0, at=0), at=0)
    for x in range(5):
        g.max_gauge.add_momentum(+1, since=x * 4, until=x * 4 + 2)
        g.max_gauge.add_momentum(-1, since=x * 4 + 2, until=x * 4 + 4)
        g.min_gauge.add_momentum(-1, since=x * 4, until=x * 4 + 2)
        g.min_gauge.add_momentum(+1, since=x * 4 + 2, until=x * 4 + 4)
    for x in range(4):
        t = sum(y * 2 for y in range(x + 1))
        g.add_momentum(+1, since=t, until=t + (x + 1))
        g.add_momentum(-1, since=t + (x + 1), until=t + 2 * (x + 1))
    assert g.determination == [
        (0, 2), (1, 3), (2, 2), (3.5, 3.5), (4, 3), (6, 1), (8, 3), (9, 4),
        (11.5, 1.5), (12, 2), (14.5, 4.5), (16, 3), (18.5, 0.5), (20, 2)]


def test_hypergauge_hybrid1():
    # hybrid 1: same velocity of `g` and `g.max_gauge`.
    # (suggested by @hybrid0)
    g = Gauge(0, Gauge(1, 5, at=0), at=0)
    g.add_momentum(+1)
    g.max_gauge.add_momentum(+1, since=1)
    assert g.determination == [(0, 0), (1, 1), (5, 5)]


def test_hypergauge_hybrid2():
    # hybrid 2: velocity of `g.max_gauge` is faster than `g`'s.
    g = Gauge(0, Gauge(1, 5, at=0), at=0)
    g.add_momentum(+1)
    g.max_gauge.add_momentum(+2, since=1)
    assert g.determination == [(0, 0), (1, 1), (5, 5)]


def test_hypergauge_hybrid3():
    # hybrid 3: velocity of `g.max_gauge` is slower than `g`'s.
    g = Gauge(0, Gauge(1, 5, at=0), at=0)
    g.add_momentum(+1)
    g.max_gauge.add_momentum(+0.5, since=1)
    assert g.determination == [(0, 0), (1, 1), (9, 5)]


def test_hyper_hypergauge(zigzag, bidir):
    # under zigzag 1
    g = Gauge(1, zigzag, at=0)
    g.add_momentum(+0.5)
    assert round_determination(g.determination, precision=2) == [
        (0, 1), (1.33, 1.67), (2, 1), (4, 2), (5.5, 0.5), (9.5, 2.5),
        (10, 2), (11.5, 0.5), (12.5, 1)]
    # between zigzag 1 ~ bidirectional hyper-gauge
    g = Gauge(3, bidir, zigzag, at=0)
    g.add_momentum(+3, since=0, until=3)
    g.add_momentum(-3, since=3, until=6)
    g.add_momentum(+3, since=6, until=9)
    g.add_momentum(-3, since=9, until=12)
    assert round_determination(g.determination, precision=2) == [
        (0, 3), (1, 6), (2.5, 7.5), (3, 7), (5, 1), (5.5, 0.5), (6, 1),
        (8, 7), (9, 7), (11, 1), (11.5, 0.5), (12, 1)]


def test_hypergauge_with_different_base_time():
    g = Gauge(0, Gauge(10, 100, at=100), at=0)
    g.add_momentum(+1)
    assert g.max_gauge.get(0) == 10
    assert g.get(10) == 10
    g = Gauge(0, Gauge(10, 100, at=0), at=100)
    g.add_momentum(+1)
    assert g.max_gauge.get(100) == 10
    assert g.get(110) == 10


def test_limited_gauges():
    max_g = Gauge(10, 100, at=0)
    g = Gauge(0, max_g, at=0)
    assert g in max_g.limited_gauges()
    g.set_max(10, at=0)
    assert g not in max_g.limited_gauges()
    # clear dead links.
    g.set_max(max_g, at=0)
    assert len(max_g.limited_gauges()) == 1
    del g
    # NOTE: Weak references could not be collected by GC immediately in PyPy.
    for x in range(10):
        try:
            assert len(max_g.limited_gauges()) == 0
        except AssertionError:
            continue
        else:
            break


def test_over_max_on_hypergauge():
    g = Gauge(1, Gauge(10, 20, at=0), at=0)
    g.max_gauge.add_momentum(+1)
    with pytest.raises(ValueError):
        g.set(20, at=0)
    g.set(20, at=0, outbound=OK)
    assert g.get(at=0) == 20
    g.set(20, at=10)
    assert g.get(at=10) == 20
    assert g.get(at=0) == 20  # past was forgot


def test_pickle_hypergauge():
    # case 1 from :func:`test_hypergauge`.
    g = Gauge(12, 100, at=0)
    g.add_momentum(+1, since=1, until=6)
    g.add_momentum(-1, since=3, until=8)
    g.set_max(Gauge(15, 15, at=0), at=0)
    g.max_gauge.add_momentum(-1, until=5)
    assert g.determination == [
        (0, 12), (1, 12), (2, 13), (3, 12), (5, 10), (6, 10), (8, 8)]
    assert g.max_gauge.determination == [(0, 15), (5, 10)]
    data = pickle.dumps(g)
    g2 = pickle.loads(data)
    assert g2.max_gauge is not None
    assert g2.determination == [
        (0, 12), (1, 12), (2, 13), (3, 12), (5, 10), (6, 10), (8, 8)]
    assert g2.max_gauge.determination == [(0, 15), (5, 10)]
    assert g2 in g2.max_gauge.limited_gauges()


def test_thin_momenta():
    g = Gauge(0, 100, at=0)
    for x in range(1000):
        g.add_momentum(+1000000000, since=x, until=x + 1e-10)
    assert_all_in_range(g)
    assert g.get(0) == 0
    assert g.get(1001) == 100
    for x, y in zip(range(9999), range(1, 10000)):
        assert 0 <= g.get(x / 10.) <= g.get(y / 10.) <= 100


def test_clear_momentum_events():
    g = Gauge(0, 10, at=0)
    m = g.add_momentum(+1, since=10, until=20)
    assert list(g.momentum_events()) == \
        [(0, NONE, None), (10, ADD, m), (20, REMOVE, m), (+inf, NONE, None)]
    # assert len(g._events) == 2
    g.remove_momentum(m)
    assert list(g.momentum_events()) == [(0, NONE, None), (+inf, NONE, None)]
    # assert len(g._events) == 0


def test_decr_max_normal():
    g = Gauge(0, 10, at=0)
    g.add_momentum(+2)
    g.add_momentum(-1)
    assert g.base[TIME] == 0
    assert g.get(10) == 10
    g.set_max(5, at=10)
    g.set(10, outbound=OK, at=10)
    assert g.base[TIME] == 10
    assert g.get(10) == 10
    assert g.get(15) == 5
    assert g.get(20) == 5


def test_decr_max_hyper():
    g = Gauge(0, Gauge(10, 100, at=0), at=0)
    g.add_momentum(+2)
    g.add_momentum(-1)
    assert g.base[TIME] == 0
    assert g.get(10) == 10
    g.max_gauge.decr(5, at=10)
    assert g.base[TIME] == 10
    assert g.get(10) == 5
    assert g.get(20) == 5


def test_decr_max_skewed_hyper():
    # skewed hyper-gauge
    g = Gauge(0, Gauge(10, 100, at=10), at=0)
    g.add_momentum(+2)
    g.add_momentum(-1)
    assert g.base[TIME] == 0
    assert g.get(10) == 10
    g.max_gauge.decr(5, at=10)
    assert g.base[TIME] == 10
    assert g.get(10) == 5
    assert g.get(20) == 5


def test_decr_max_before_base_time():
    # decr max earlier than the gauge's base time.
    g = Gauge(0, Gauge(10, 100, at=10), at=5)
    g.add_momentum(+1)
    assert g.determination == [(5, 0), (15, 10)]

    with pytest.raises(ValueError):
        g.max_gauge.decr(5, at=0)
    assert g.determination == [(5, 0), (15, 10)]

    g.max_gauge.incr(10, at=10)
    assert g.determination == [(10, 5), (25, 20)]


def test_hypergauge_past_bugs(zigzag, bidir):
    """Regression testing for hyper-gauge."""
    # just one momentum
    g1 = Gauge(5, Gauge(5, 10, at=0), Gauge(5, 10, at=0), at=0)
    g1.max_gauge.add_momentum(+1)
    g1.min_gauge.add_momentum(-1)
    assert g1.determination == [(0, 5)]
    g1.add_momentum(+0.1, until=100)
    assert g1.determination == [(0, 5), (50, 10), (100, 10)]
    # floating-point inaccuracy problem 1
    g1 = Gauge(3, bidir, zigzag, at=0)
    g1.add_momentum(+6, since=0, until=1)
    g1.add_momentum(-6, since=1, until=2)
    g1.add_momentum(+6, since=2, until=3)
    g1.add_momentum(-6, since=3, until=4)
    g1.add_momentum(+6, since=4, until=5)
    g1.add_momentum(-6, since=5, until=6)
    g1.add_momentum(+6, since=6, until=7)
    g1.add_momentum(-6, since=7, until=8)
    g1.add_momentum(+6, since=8, until=9)
    g1.add_momentum(-6, since=9, until=10)
    g1.add_momentum(+6, since=10, until=11)
    g1.add_momentum(-6, since=11, until=12)
    assert round_determination(g1.determination, precision=2) == [
        (0, 3), (0.4, 5.4), (1, 6), (1.8, 1.2), (2, 1), (3, 7), (3.8, 2.2),
        (4, 2), (4.57, 5.43), (5, 5), (5.71, 0.71), (6, 1), (6.8, 5.8), (7, 6),
        (7.6, 2.4), (8, 2), (8.83, 7), (9, 7), (9.8, 2.2), (10, 2),
        (10.57, 5.43), (11, 5), (11.71, 0.71), (12, 1)]
    # float problem 2
    g2 = Gauge(0, Gauge(1, 1, at=0), at=0)
    for x in range(10):
        g2.add_momentum(+0.1, since=x, until=x + 1)
    g2.max_gauge.add_momentum(-0.1, since=0, until=6)
    g2.max_gauge.add_momentum(+0.5, since=6, until=10)
    assert round(g2.get(5), 1) == 0.5
    assert round(g2.get(6), 1) == 0.4
    assert round(g2.get(7), 1) == 0.5
    assert round(g2.get(8), 1) == 0.6
    assert round(g2.get(9), 1) == 0.7
    assert round(g2.get(10), 1) == 0.8
    # float problem 3
    g3_max_max = Gauge(3, bidir, zigzag, at=0)
    g3_max_max.add_momentum(+6, since=0, until=1)
    g3_max_max.add_momentum(-6, since=1, until=2)
    g3_max_max.add_momentum(+6, since=2, until=3)
    g3_max_max.add_momentum(-6, since=3, until=4)
    g3_max_max.add_momentum(+6, since=4, until=5)
    g3_max_max.add_momentum(-6, since=5, until=6)
    g3_max_max.add_momentum(+6, since=6, until=7)
    g3_max_max.add_momentum(-6, since=7, until=8)
    g3_max_max.add_momentum(+6, since=8, until=9)
    g3_max_max.add_momentum(-6, since=9, until=10)
    g3_max_max.add_momentum(+6, since=10, until=11)
    g3_max_max.add_momentum(-6, since=11, until=12)
    g3_max = Gauge(0, g3_max_max, at=0)
    for x in range(10):
        g3_max.add_momentum(+0.1, since=x)
    r = random.Random(10)
    g3 = Gauge(0, shift_gauge(zigzag, +3), g3_max, at=0)
    for x in range(10):
        g3.add_momentum(r.uniform(-10, 10), since=x, until=x + 1)
    assert round(g3.get(9), 1) == 2.9  # not 2.4133871928
    # bound at first
    g4 = Gauge(0, 10, Gauge(0, 10, at=1), at=0)
    g4.min_gauge.add_momentum(+1, until=11)
    g4.add_momentum(-1, until=10)
    assert g4.get(10) == 9  # not -10
    assert g4.determination == [(0, 0), (1, 0), (10, 9), (11, 10)]
    # floor is dense than ceil
    r = random.Random(2810856076715324514)
    g5 = Gauge(0, shift_gauge(zigzag, +3), g3, at=0)
    for x in range(4):
        g5.add_momentum(r.uniform(-10, 10), since=x, until=x + 1)
    assert round(g5.get(4), 1) == 5.0  # not 11.8


def assert_all_in_range(g, message=None):
    outbound = True
    for t, v in g.determination:
        for v in [v, g.get(t)]:
            in_range = g.get_min(t) <= v <= g.get_max(t)
            if in_range:
                outbound = False
                continue
            elif outbound:
                continue
            # from gaugeplot import show_gauge
            # show_gauge(g)
            report = ('[{0!r}] {1!r} <= {2!r} <= {3!r}'
                      ''.format(t, g.get_min(t), v, g.get_max(t)))
            if message is None:
                message = report
            else:
                message = '\n'.join([message, report])
            pytest.fail(message)


def random_gauge1(random=random, far=10, near=3, until=20):
    # (-far ~ -near) <= g <= (near ~ far)
    g_max = Gauge(random.uniform(near, far), far, near, at=0)
    g_min = Gauge(random.uniform(-far, -near), -near, -far, at=0)
    value = random.uniform(g_min.min_value, g_max.max_value)
    g = Gauge(value, g_max, g_min, at=0)
    for x in range(0, until, 5):
        g_max.add_momentum(random.uniform(-far, +far), since=x, until=x + 5)
    for x in range(0, until, 2):
        g.add_momentum(random.uniform(-far, +far), since=x, until=x + 2)
    for x in range(0, until, 1):
        g_min.add_momentum(random.uniform(-far, +far), since=x, until=x + 1)
    return g


def random_gauge2(random=random, far=1000, near=1, until=20):
    # 0 <= g <= (near ~ far)
    g_max = Gauge(random.uniform(near, far), far, near, at=0)
    value = random.uniform(0, g_max.max_value)
    g = Gauge(value, g_max, at=0)
    for x in range(0, until, 5):
        g_max.add_momentum(random.uniform(-far, +far), since=x, until=x + 5)
    for x in range(0, until, 2):
        g.add_momentum(random.uniform(-far, +far), since=x, until=x + 2)
    return g


def test_randomly():
    times = 100
    maxint = 2 ** 64 / 2
    for y in range(times):
        seed = random.randrange(maxint)
        g = random_gauge1(Random(seed))
        assert_all_in_range(g, 'random_gauge1(R({0}))'.format(seed))
    for y in range(times):
        seed = random.randrange(maxint)
        g = random_gauge1(Random(seed), far=1000)
        assert_all_in_range(g, 'random_gauge1(R({0}), far=1000)'.format(seed))
    for y in range(times):
        seed = random.randrange(maxint)
        g = random_gauge1(Random(seed), near=1e-10)
        assert_all_in_range(g, 'random_gauge1(R({0}), near=1e-10)'
                               ''.format(seed))
    for y in range(times):
        seed = random.randrange(maxint)
        g = random_gauge2(Random(seed), far=1e4)
        assert_all_in_range(g, 'random_gauge2(R({0}), far=1e4)'.format(seed))


@pytest.mark.parametrize('seed', [5425676250556669398, 5788334089912086268])
def test_cpu_hang(seed):
    g = random_gauge1(Random(seed))
    assert_all_in_range(g, 'random_gauge1(R({0}))'.format(seed))


def test_repaired_random_gauges():
    # from test_randomly()
    assert_all_in_range(random_gauge1(Random(1098651790867685487)))
    assert_all_in_range(random_gauge1(Random(957826144573409526)))
    assert_all_in_range(random_gauge1(Random(7276062123994486117), near=1e-10))
    assert_all_in_range(random_gauge1(Random(6867673013126676888), near=1e-10))
    assert_all_in_range(random_gauge1(Random(8038810374719555655), near=1e-10))
    assert_all_in_range(random_gauge1(Random(5925612648020704501), near=1e-10))
    assert_all_in_range(random_gauge1(Random(2881266403492433952), far=1000))
    assert_all_in_range(random_gauge1(Random(6468976982055982554), far=1000))
    assert_all_in_range(random_gauge2(Random(3373542927760325757), far=1e6))
    assert_all_in_range(random_gauge2(Random(7588425536572564538), far=1e4))


def test_clamp_on_get():
    g = random_gauge1(Random(6883875130559908307))
    at = 14.803740162409357
    e = 00.000000000000001
    g.clear_momenta(at=at)
    for x in range(-100, +100):
        t = at + x * e
        assert g.get_min(t) <= g.get(t)


def test_false_accusation():
    g = random_gauge1(Random(6883875130559908307))
    assert g.get(15) == -3
    g.incr(0, at=14.803740162409364)
    assert g.get(15) == -3
    g.incr(0, at=14.803740162409365)
    assert g.get(15) == -3


def test_goal():
    g = Gauge(100, 100, at=0)
    assert g.goal() == 100
    g.add_momentum(-1)
    assert g.goal() == 0
    g.add_momentum(+1)
    assert g.goal() == 100
    g.add_momentum(-1, since=10000, until=10001)
    assert g.goal() == 99


def test_clamped_by_max_gauge():
    # in_range, decr max -> clamp
    g = Gauge(10, Gauge(20, 20, at=0), at=0)
    assert g.get(0) == 10
    g.max_gauge.set(5, at=0)
    assert g.get(0) == 5
    # in_range, incr max -> not clamp
    g.max_gauge.set(15, at=0)
    assert g.get(0) == 5
    # outbound, decr max -> not clamp
    g.set(20, outbound=OK, at=0)
    assert g.get(0) == 20
    g.max_gauge.set(10, at=0)
    assert g.get(0) == 20
    # time-skewed
    g = Gauge(10, Gauge(20, 20, at=0), at=0)
    g.max_gauge.set(5, at=10)
    assert g.base[TIME] == 10
    assert g.base[VALUE] == 5


def test_set_range():
    g = Gauge(0, 100, at=0)
    g.add_momentum(+1)
    assert g.determination == [(0, 0), (100, 100)]
    g.set_range(Gauge(100, 100, at=0), Gauge(0, 100, at=0), at=0)
    g.max_gauge.add_momentum(-1, until=40)
    g.min_gauge.add_momentum(+1, until=40)
    assert g.determination == [(0, 0), (60, 60)]
    g.clear_momenta(at=30)
    g.add_momentum(-1)
    assert g.determination == [(30, 30), (40, 40)]


def test_in_range():
    g = Gauge(20, 10, at=0)
    assert not g.in_range(0)
    assert not g.in_range(20)
    g.add_momentum(-1)
    assert not g.in_range(0)
    assert g.in_range(20)


def test_clamp():
    g = Gauge(20, max=10, min=0, at=0)
    assert g.clamp(at=0) == 10
    g = Gauge(-10, max=10, min=0, at=0)
    assert g.clamp(at=0) == 0


def test_momentum_event_order():
    class MyGauge(Gauge):
        def _make_momentum(self, m):
            return m
    g = MyGauge(0, 100, at=0)
    m = Momentum(+1, since=10, until=10)
    g.add_momentum(m)
    assert \
        list(g.momentum_events()) == \
        [(0, NONE, None), (10, ADD, m), (10, REMOVE, m), (+inf, NONE, None)]


def test_case7():
    f = FakeGauge([(0, 0), (1, 1)])
    g = Gauge(3.5, f, at=-1)
    g.add_momentum(-2)
    g.add_momentum(+1)
    assert g.determination == [(-1, 3.5), (0.5, 0.5), (1, 0)]


def test_case7_reversed():
    f = FakeGauge([(0, 0), (1, -1)])
    g = Gauge(-3.5, 0, f, at=-1)
    g.add_momentum(+2)
    g.add_momentum(-1)
    assert g.determination == [(-1, -3.5), (0.5, -0.5), (1, 0)]


def test_case8():
    """There's a hyper-gauge.  When the same effects are affected twice, the
    underlying gauge became to be out of the limited range.
    """
    m = Gauge(679, 679, at=1503918965.158631)
    m.add_momentum(+0.001157)

    g = Gauge(679, m, at=1503918965.158631)
    g.add_momentum(+1)

    # Gauge "g" should be always in the range of "m".
    def G_SHOULD_BE_FULLY_IN_RANGE():
        assert g.determination.in_range_since == g.base[TIME]

    G_SHOULD_BE_FULLY_IN_RANGE()

    # first effect ------------------------------------------------------------

    m.forget_past(at=1503919261.248346)
    G_SHOULD_BE_FULLY_IN_RANGE()

    m.add_momentum(0, since=1503919261.248346, until=1503919266.248346)
    m.forget_past(at=1503919261.248346)
    G_SHOULD_BE_FULLY_IN_RANGE()

    m.add_momentum(-0.2, since=1503919261.248346, until=1503919561.248346)
    G_SHOULD_BE_FULLY_IN_RANGE()

    # second effect -----------------------------------------------------------

    m.forget_past(at=1503919279.381339)
    G_SHOULD_BE_FULLY_IN_RANGE()

    m.forget_past(at=1503919279.381339)
    G_SHOULD_BE_FULLY_IN_RANGE()

    m.add_momentum(0, since=1503919279.381339, until=1503919284.381339)
    G_SHOULD_BE_FULLY_IN_RANGE()

    m.forget_past(at=1503919279.482356)
    m.remove_momentum(-0.2, since=1503919261.248346, until=1503919561.248346)
    G_SHOULD_BE_FULLY_IN_RANGE()

    with pytest.raises(ValueError):
        m.forget_past(at=1503919279.381339)
    m.add_momentum(-0.2, since=1503919279.381339, until=1503919579.381339)
    G_SHOULD_BE_FULLY_IN_RANGE()  # failing!

    m.forget_past(at=1503919287.680848)
    G_SHOULD_BE_FULLY_IN_RANGE()  # failing!


def test_case8_simple():
    max_ = Gauge(10, 10, at=0)
    max_.add_momentum(-1)

    g = Gauge(10, max_, at=0)

    max_.forget_past(at=2)

    with pytest.raises(ValueError):
        max_.forget_past(at=1)  # forget older past.

    assert g.get(99999) == approx(0)


def test_intersection_of_vertical_segment():
    assert 0 != 1e-309
    assert math.isinf(1 / 1e-309)
    f = FakeGauge([(0, 0), (1e-309, 1)])
    assert f.get(0.000000000000000000000) == 0
    assert f.get(0.000000000000000000001) == 1
    g = Gauge(2.5, f, at=-1)
    g.add_momentum(-2)
    g.add_momentum(+1)
    assert \
        round_determination(g.determination, precision=1) == \
        [(-1, 2.5), (0, 0.5), (0.5, 0)]


def test_intersection_of_vertical_segment_reversed():
    f = FakeGauge([(0, 0), (1e-309, -1)])
    g = Gauge(-2.5, 0, f, at=-1)
    g.add_momentum(+2)
    g.add_momentum(-1)
    assert \
        round_determination(g.determination, precision=1) == \
        [(-1, -2.5), (0, -0.5), (0.5, 0)]


def test_invalidate_returns():
    g = Gauge(0, 100, at=0)
    assert not g.invalidate()
    g.get(0)
    assert g.invalidate()
    assert not g.invalidate()
