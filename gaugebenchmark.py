# -*- coding: utf-8 -*-
import cPickle as pickle
from random import Random

import pytest

from gauge import Gauge
from gauge.deterministic import Determination


@pytest.fixture(scope='module', params=[0, 100])
def g(request):
    length = request.param
    g = Gauge(0, 10, at=0)
    r = Random(length)
    for x in range(length):
        since = r.randrange(1000)
        until = since + 1 + r.randrange(1000)
        g.add_momentum(r.uniform(-10, +10), since=since, until=until)
    return g


def test_pickle_dump(benchmark, g):
    benchmark(lambda: pickle.dumps(g))


def test_pickle_load(benchmark, g):
    d = pickle.dumps(g)
    benchmark(lambda: pickle.loads(d))


def test_determination(benchmark, g):
    benchmark(lambda: Determination(g))
