# -*- coding: utf-8 -*-
from gauge import Gauge, OK, CLAMP


__all__ = [b'StaticGauge']


class StaticGauge(Gauge):

    @property
    def determination(self):
        return [self.base]

    def add_momentum(self, *args, **kwargs):
        raise TypeError('StaticGauge doesn\'t allow adding a momentum')

    def remove_momentum(self, *args, **kwargs):
        raise TypeError('StaticGauge doesn\'t have any momentum')

    def _set_limits(self, max_=None, min_=None, *args, **kwargs):
        if isinstance(max_, Gauge) or isinstance(min_, Gauge):
            raise TypeError('StaticGauge cannot be a hyper-gauge')
        super(StaticGauge, self)._set_limits(max_, min_, *args, **kwargs)

    '''
    def __getstate__(self):
        return (self.base, self._max, self._min)

    def __setstate__(self, state):
        base, max_, min_ = state
        self.__init__(base[VALUE], max=max_, min=min_, at=base[TIME])
    '''


def test_static_gauge():
    import pytest
    g = StaticGauge(10, 100, at=0)
    assert g.get(0) == 10
    assert g.get(100) == 10
    g.incr(10)
    assert g.get() == 20
    with pytest.raises(ValueError):
        g.incr(100)
    g.incr(100, outbound=CLAMP)
    assert g.get() == 100
    g.incr(10, outbound=OK)
    assert g.get() == 110
    with pytest.raises(TypeError):
        g.add_momentum(+1)
    with pytest.raises(TypeError):
        g.remove_momentum(+1)
