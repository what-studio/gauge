# -*- coding: utf-8 -*-
from contextlib import contextmanager
import time

import pytest

from gauge import Gauge, Momentum


@contextmanager
def t(timestamp):
    orig_time = time.time
    time.time = lambda: float(timestamp)
    try:
        yield
    finally:
        time.time = orig_time


def test_in_range():
    g = Gauge(12, 0, 100, at=0)
    g.add_momentum(+1, since=1, until=6)
    g.add_momentum(-1, since=3, until=8)
    assert list(g.determine()) == [(0, 12), (1, 12), (3, 14), (6, 14), (8, 12)]


def test_over_max():
    g = Gauge(8, 0, 10, at=0)
    g.add_momentum(+1, since=0, until=4)
    assert list(g.determine()) == [(0, 8), (2, 10), (4, 10)]
    g = Gauge(12, 0, 10, at=0)
    g.add_momentum(-1, since=0, until=4)
    assert list(g.determine()) == [(0, 12), (2, 10), (4, 8)]
    g = Gauge(12, 0, 10, at=0)
    g.add_momentum(+1, since=0, until=4)
    g.add_momentum(-2, since=0, until=4)
    assert list(g.determine()) == [(0, 12), (1, 10), (4, 7)]
    g = Gauge(12, 0, 10, at=0)
    g.add_momentum(+1, since=1, until=6)
    g.add_momentum(-1, since=3, until=8)
    g.add_momentum(+1, since=10, until=14)
    g.add_momentum(-1, since=13, until=16)
    assert list(g.determine()) == [
        (0, 12), (1, 12), (3, 12), (5, 10), (6, 10), (8, 8),
        (10, 8), (12, 10), (13, 10), (14, 10), (16, 8)]


def test_under_min():
    g = Gauge(2, 0, 10, at=0)
    g.add_momentum(-1, since=0, until=4)
    assert list(g.determine()) == [(0, 2), (2, 0), (4, 0)]
    g = Gauge(-2, 0, 10, at=0)
    g.add_momentum(+1, since=0, until=4)
    assert list(g.determine()) == [(0, -2), (2, 0), (4, 2)]
    g = Gauge(-2, 0, 10, at=0)
    g.add_momentum(-1, since=0, until=4)
    g.add_momentum(+2, since=0, until=4)
    assert list(g.determine()) == [(0, -2), (1, 0), (4, 3)]
    g = Gauge(-2, 0, 10, at=0)
    g.add_momentum(-1, since=1, until=6)
    g.add_momentum(+1, since=3, until=8)
    g.add_momentum(-1, since=10, until=14)
    g.add_momentum(+1, since=13, until=16)
    assert list(g.determine()) == [
        (0, -2), (1, -2), (3, -2), (5, 0), (6, 0), (8, 2),
        (10, 2), (12, 0), (13, 0), (14, 0), (16, 2)]


def test_permanent():
    g = Gauge(10, 0, 10, at=0)
    g.add_momentum(-1)
    assert list(g.determine()) == [(0, 10), (10, 0)]
    g = Gauge(0, 0, 10, at=0)
    g.add_momentum(+1)
    assert list(g.determine()) == [(0, 0), (10, 10)]
    g = Gauge(12, 0, 10, at=0)
    g.add_momentum(-1)
    assert list(g.determine()) == [(0, 12), (2, 10), (12, 0)]
    g = Gauge(5, 0, 10, at=0)
    g.add_momentum(+1, since=3)
    assert list(g.determine()) == [(0, 5), (3, 5), (8, 10)]
    g = Gauge(5, 0, 10, at=0)
    g.add_momentum(+1, until=8)
    assert list(g.determine()) == [(0, 5), (5, 10), (8, 10)]


def test_life():
    with t(0):
        life = Gauge(100, max=100)
        life.add_momentum(-1)
        assert life.current() == 100
    with t(1):
        assert life.current() == 99
    with t(2):
        assert life.current() == 98
    with t(10):
        assert life.current() == 90
        life.incr(1)
        assert life.current() == 91
    with t(11):
        assert life.current() == 90


def test_no_momentum():
    g = Gauge(1, max=10, at=0)
    assert list(g.determine()) == [(0, 1)]
    assert g.current() == 1


def test_limit():
    g = Gauge(1, max=10)
    with pytest.raises(ValueError):
        g.set(11)
    g.set(10)
    assert g.current() == 10
    g.set(11, limit=False)
    assert g.current() == 11


def test_case1():
    g = Gauge(0, max=5, at=0)
    g.add_momentum(+1)
    g.add_momentum(-2, since=1, until=3)
    g.add_momentum(+1, since=5, until=7)
    assert list(g.determine()) == [
        (0, 0), (1, 1), (2, 0), (3, 0), (5, 2), (6.5, 5), (7, 5)]


def test_case2():
    g = Gauge(12, max=10, at=0)
    g.add_momentum(+2, since=2, until=10)
    g.add_momentum(-1, since=4, until=8)
    assert list(g.determine()) == [
        (0, 12), (2, 12), (4, 12), (6, 10), (8, 10), (10, 10)]


def test_case3():
    g = Gauge(0, max=10, at=0)
    assert g.current(0) == 0
    g.add_momentum(+1, since=0)
    assert g.current(10) == 10
    g.incr(3, limit=False, at=11)
    assert g.current(11) == 13
    g.add_momentum(-1, since=13)
    assert g.current(13) == 13
    assert g.current(14) == 12
    assert g.current(15) == 11
    assert g.current(16) == 10
    assert g.current(17) == 10
