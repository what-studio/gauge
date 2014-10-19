# -*- coding: utf-8 -*-
"""A recipe to implement named gauge. Named gauge keeps momenta and their
names. You can manipulate a specific momentum by the name you named.

Test it by `py.test <http://pytest.org/>`_:

.. sourcecode:: console

   $ py.test recipes/namedgauge.py

"""
from collections import namedtuple

from gauge import Gauge, Momentum, now_or


class NamedMomentum(namedtuple('_', 'velocity, since, until, name'), Momentum):

    pass


class NamedGauge(Gauge):

    def _make_momentum(self, velocity_or_momentum,
                       since=None, until=None, name=None):
        base = super(NamedGauge, self)
        momentum = base._make_momentum(velocity_or_momentum, since, until)
        if not isinstance(momentum, NamedMomentum):
            velocity, since, until = momentum
            momentum = NamedMomentum(velocity, since, until, name)
        return momentum

    def get_momentum_by_name(self, name):
        """Gets a momentum by the given name.

        :param name: the momentum name.

        :returns: a momentum found.

        :raises TypeError: `name` is ``None``.
        :raises KeyError: failed to find a momentum named `name`.
        """
        if name is None:
            raise TypeError('\'name\' should not be None')
        for momentum in self.momenta:
            if momentum.name == name:
                return momentum
        raise KeyError('No such momentum named {0}'.format(name))

    def pop_momentum_by_name(self, name):
        """Removes and returns a momentum by the given name.

        :param name: the momentum name.

        :returns: a momentum removed.

        :raises TypeError: `name` is ``None``.
        :raises KeyError: failed to find a momentum named `name`.
        """
        momentum = self.get_momentum_by_name(name)
        self.remove_momentum(momentum)
        return momentum

    def update_momentum_by_name(self, name, **kwargs):
        """Updates a momentum by the given name.

        :param name: the momentum name.
        :param velocity: (keyword-only) a new value for `velocity`.
        :param since: (keyword-only) a new value for `since`.
        :param until: (keyword-only) a new value for `until`.

        :returns: a momentum updated.

        :raises TypeError: `name` is ``None``.
        :raises KeyError: failed to find a momentum named `name`.
        """
        momentum = self.pop_momentum_by_name(name)
        velocity, since, until = momentum[:3]
        velocity = kwargs.get('velocity', velocity)
        since = kwargs.get('since', since)
        until = kwargs.get('until', until)
        return self.add_momentum(velocity, since, until, name)

    def snap_momentum_by_name(self, name, velocity, at=None):
        """Changes the velocity of a momentum named `name`.

        :param name: the momentum name.
        :param velocity: a new velocity.
        :param at: the time to snap. (default: now)

        :returns: a momentum updated.

        :raises TypeError: `name` is ``None``.
        :raises KeyError: failed to find a momentum named `name`.
        """
        at = now_or(at)
        self.incr(0, at=at)
        return self.update_momentum_by_name(name, velocity=velocity, since=at)


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


def test_get_momentum_by_name():
    import pytest
    g = NamedGauge(50, 100, at=0)
    g.add_momentum(+1, since=0, until=10)
    g.add_momentum(+2, since=0, until=10)
    g.add_momentum(+3, since=0, until=10, name='test')
    with pytest.raises(TypeError):
        g.get_momentum_by_name(None)
    m = g.get_momentum_by_name('test')
    assert m.velocity == +3
    assert m.name == 'test'


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


def test_snap_momentum_by_name():
    g = NamedGauge(50, 100, at=0)
    g.add_momentum(-1)
    g.add_momentum(+2, since=0, until=10, name='test')
    assert g.get(1) == 51
    assert g.get(5) == 55
    assert g.get(10) == 60
    assert g.get(20) == 50
    g.snap_momentum_by_name('test', +3, at=5)
    assert g.get(1) == 55  # the past was forgotten.
    assert g.get(5) == 55  # but the gauge remembers the effect from the past.
    assert g.get(10) == 65
    assert g.get(20) == 55


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
        g.remove_momentum(-1, since=1, until=11, name='no-name')
    g.remove_momentum(-1, since=1, until=11, name='bar')
    assert g.velocity(5) == -1
