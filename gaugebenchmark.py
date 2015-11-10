# -*- coding: utf-8 -*-
import cPickle as pickle
from random import Random

import pytest

from gauge import CLAMP, Gauge
from gauge.deterministic import Determination


r = Random(42)
pickle_protocols = list(range(pickle.HIGHEST_PROTOCOL + 1))


@pytest.fixture(scope='module', params=[0, 10, 100])
def g(request):
    length = request.param
    g = Gauge(0, 10, at=0)
    for x in range(length):
        add_random_momentum(g)
    return g


def add_random_momentum(g):
    since = r.randrange(1000)
    until = since + 1 + r.randrange(1000)
    g.add_momentum(r.uniform(-10, +10), since=since, until=until)


@pytest.mark.parametrize('pickle_protocol', pickle_protocols)
def test_pickle_dump(benchmark, pickle_protocol, g):
    benchmark(lambda: pickle.dumps(g, pickle_protocol))


@pytest.mark.parametrize('pickle_protocol', pickle_protocols)
def test_pickle_load(benchmark, pickle_protocol, g):
    d = pickle.dumps(g, pickle_protocol)
    benchmark(lambda: pickle.loads(d))


def test_determination(benchmark, g):
    benchmark(lambda: Determination(g))


def test_incr(benchmark, g):
    benchmark(lambda: g.incr(r.uniform(-10, +10), CLAMP, r.randrange(1000)))


def test_add_momentum(benchmark, g):
    benchmark(lambda: add_random_momentum(g))


def test_get(benchmark, g):
    g.determination
    benchmark(lambda: g.get(r.randrange(1000)))
