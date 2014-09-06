# -*- coding: utf-8 -*-
from collections import namedtuple

from gauge import Gauge, Momentum


_NamedMomentum = \
    namedtuple('NamedMomentum', ['velocity', 'since', 'until', 'name'])


class NamedMomentum(_NamedMomentum, Momentum):

    pass


class NamedGauge(Gauge):

    def _make_momentum(self, velocity_or_momentum,
                       since=None, until=None, name=None):
        base = super(NamedGauge, self)
        momentum = base._make_momentum(velocity_or_momentum, since, until)
        velocity, since, until = momentum[:3]
        try:
            name = momentum.name
        except AttributeError:
            pass
        return NamedMomentum(velocity, since, until, name)

    def get_momentum_by_name(self, name):
        for momentum in self.momenta:
            if momentum.name == name:
                return momentum
        raise KeyError('No such momentum named {0}'.format(name))

    def pop_momentum_by_name(self, name):
        momentum = self.get_momentum_by_name(name)
        self.remove_momentum(momentum)
        return momentum

    def update_momentum_by_name(self, name, **kwargs):
        momentum = self.pop_momentum_by_name(name)
        velocity, since, until = momentum[:3]
        try:
            velocity = kwargs['velocity']
        except KeyError:
            pass
        try:
            since = kwargs['since']
        except KeyError:
            pass
        try:
            until = kwargs['until']
        except KeyError:
            pass
        self.add_momentum(velocity, since, until, name)


def test_basic():
    g = NamedGauge(50, 100, at=0)
    g.add_momentum(+1, since=0, until=10)
    assert g.get(0) == 50
    assert g.get(1) == 51
    assert g.get(10) == 60


def test_consistency():
    g = NamedGauge(50, 100, at=0)
    g.add_momentum(+1, since=0, until=10, name='test')
    assert g.get(0) == 50
    assert g.get(1) == 51
    assert g.get(10) == 60


def test_named_momentum():
    g = NamedGauge(50, 100, at=0)
    m = g.add_momentum(+1, since=0, until=10)
    assert isinstance(m, NamedMomentum)


def test_pop_momentum_by_name():
    g = NamedGauge(50, 100, at=0)
    g.add_momentum(+1, since=0, until=10, name='test')
    assert g.get(10) == 60
    g.pop_momentum_by_name('test')
    assert g.get(10) == 50


def test_update_momentum_by_name():
    g = NamedGauge(50, 100, at=0)
    g.add_momentum(+1, since=0, until=10, name='test')
    assert g.get(15) == 60
    g.update_momentum_by_name('test', until=20)
    assert g.get(15) == 65


def test_multiple_momenta():
    import pytest
    g = NamedGauge(50, 100, at=0)
    g.add_momentum(+1, since=0, until=10, name='foo')
    g.add_momentum(-1, since=1, until=11, name='bar')
    g.add_momentum(-1, since=1, until=11, name='baz')
    assert g.velocity(5) == -1
    g.pop_momentum_by_name('foo')
    assert g.velocity(5) == -2
    with pytest.raises(ValueError):
        g.remove_momentum(-1, since=1, until=11)
    g.remove_momentum(-1, since=1, until=11, name='bar')
    assert g.velocity(5) == -1