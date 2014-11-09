# -*- coding: utf-8 -*-
from gauge import Gauge


__all__ = [b'FrozenGauge']


class FrozenGauge(Gauge):

    def __init__(self, gauge):
        cls, _max, _min = type(self), gauge.max, gauge.min
        self._max = cls(_max) if isinstance(_max, Gauge) else _max
        self._min = cls(_min) if isinstance(_min, Gauge) else _min
        self._determination = gauge.determination

    @property
    def base(self):
        raise TypeError('FrozenGauge doesn\'t keep the base')

    @property
    def momenta(self):
        raise TypeError('FrozenGauge doesn\'t keep the momenta')

    def __getstate__(self):
        return (self._max, self._min, self._determination)

    def __setstate__(self, state):
        self._max, self._min, self._determination = state

    def invalidate(self):
        raise AssertionError('FrozenGauge cannot be invalidated')

    def _set_limits(self, *args, **kwargs):
        raise TypeError('FrozenGauge is immutable')


def test_same_determination():
    g = Gauge(10, 100, at=0)
    g.add_momentum(+1, since=5, until=10)
    g.add_momentum(+1, since=20, until=30)
    g.add_momentum(-2, since=50, until=60)
    fg = FrozenGauge(g)
    assert fg.get(0) == g.get(0) == 10
    assert fg.get(10) == g.get(10) == 15
    assert fg.get(30) == g.get(30) == 25
    assert fg.get(60) == g.get(60) == 5
    assert fg.get(100) == g.get(100) == 5


def test_immutability():
    import pytest
    fg = FrozenGauge(Gauge(10, 100, at=0))
    with pytest.raises(AssertionError):
        fg.invalidate()
    with pytest.raises(TypeError):
        fg.incr(10, at=100)
    with pytest.raises(TypeError):
        fg.decr(10, at=100)
    with pytest.raises(TypeError):
        fg.set(10, at=100)
    with pytest.raises(TypeError):
        fg.add_momentum(+1, since=10, until=20)
    with pytest.raises(TypeError):
        fg.remove_momentum(+1, since=10, until=20)
    with pytest.raises(TypeError):
        fg.max = 10
    with pytest.raises(TypeError):
        fg.min = 10
    with pytest.raises(TypeError):
        fg.forget_past(at=10)
