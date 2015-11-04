# -*- coding: utf-8 -*-
import cPickle as pickle
from random import Random

import pytest

from gauge import Gauge


@pytest.mark.parametrize('length', [0, 100])
def test_pickle(benchmark, length):
    g = Gauge(0, 10, at=0)
    r = Random(length)
    for x in range(length):
        since = r.randrange(1000)
        until = since + 1 + r.randrange(1000)
        g.add_momentum(r.uniform(-10, +10), since=since, until=until)
    benchmark(lambda: pickle.loads(pickle.dumps(g)))
