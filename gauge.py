# -*- coding: utf-8 -*-
"""
    gauge
    ~~~~~

    Deterministic gauge library.

    :copyright: (c) 2013 by Heungsub Lee
    :license: BSD, see LICENSE for more details.
"""
from collections import namedtuple
from datetime import datetime


def now_or(at):
    return datetime.utcnow() if at is None else at


class Gauge(object):

    top = None
    bottom = None
    default_momentum = None
    value_type = float

    delta = 0
    set_at = None

    def __init__(self, value, limit=True, at=None):
        if value is None:
            value = self.top
        #self.set(value, limit, at)
        self.delta = value
        self.set_at = now_or(at)
        self.momenta = []
        if self.default_momentum is not None:
            self.add_momentum(self.default_momentum)

    def add_momentum(self, momentum):
        self.momenta.append(momentum)

    def set(self, value, limit=True, at=None):
        """Sets as the given value.

        :param value: the value to set.
        :param limit: checks if the value is in the range. Defaults to ``True``.
        :param at: the datetime. Defaults to now.
        """
        at = now_or(at)
        return self.incr(value - self.current(at), limit, at)

    def incr(self, delta, limit=True, at=None):
        """Increases the value by the given delta.

        :param delta: the value to set.
        :param limit: checks if the value is in the range. Defaults to ``True``.
        :param at: the datetime. Defaults to now.
        """
        at = now_or(at)
        current = self.current(at)
        next = current + delta
        if limit:
            if delta > 0 and next > self.top:
                raise ValueError('The value to set is over the maximum')
            elif delta < 0 and next < self.bottom:
                raise ValueError('The value to set is under the minimum')
        if not self.bottom < current < self.top:
            # go to be movable by momenta
            self.set_at = at
            self.delta = next
        else:
            self.delta += delta
        #print next, self.set_at, self.delta

    def decr(self, delta, limit=True, at=None):
        """Decreases the value by the given delta."""
        return self.incr(-delta, limit, at)

    def current(self, at=None):
        """Calculates the current value."""
        #print self.delta, self.delta_moved(at)
        return self.value_type(self.delta + self.delta_moved(at))

    def delta_moved(self, at=None):
        """The delta moved by the momenta."""
        stuffs = self.stuffs(at)
        if stuffs is None:
            return 0
        return stuffs[-1] + stuffs[-2]

    def stuffs(self, at=None):
        timedelta = self.time_passed(at)
        seconds = timedelta.total_seconds()
        pos_deltas = []
        neg_deltas = []
        for momentum in self.momenta:
            delta = momentum.move(self, seconds)
            (pos_deltas if delta > 0 else neg_deltas).append(delta)
        pos_delta = sum(pos_deltas)
        neg_delta = sum(neg_deltas)
        return (
            self.delta,
            pos_delta,
            neg_delta,
            min(max(0, self.top - self.delta - neg_delta), pos_delta),
            max(min(0, self.bottom - self.delta - pos_delta), neg_delta))

    def time_passed(self, at=None):
        """The timedelta object passed from :attr:`set_at`."""
        at = now_or(at)
        return at - self.set_at

    def __eq__(self, other, at=None):
        if isinstance(other, type(self)):
            return self.__getstate__() == other.__getstate__()
        elif isinstance(other, (int, float)):
            return float(self.current(at)) == other
        return False

    def __repr__(self, at=None):
        at = now_or(at)
        current = self.current(at)
        if self.bottom == 0:
            fmt = '<{0} {1}/{2}>'
        else:
            fmt = '<{0} {1}>'
        return fmt.format(type(self).__name__, current, self.top)


class Momentum(namedtuple('Momentum', ['delta', 'interval'])):

    normalize_ticks = float

    def effects(self, gauge, at=None):
        """Weather this momentum is applying to the gauge."""
        current = gauge.current(at)
        if self.delta > 0:
            return current < gauge.top
        else:
            return current > gauge.bottom

    def move(self, gauge, seconds):
        ticks = self.normalize_ticks(seconds / self.interval)
        delta = self.delta * ticks
        return delta

    def limit(self, gauge, value):
        if self.delta > 0:
            return min(gauge.top - gauge.delta, value)
        else:
            return max(gauge.bottom - gauge.delta, value)

    def __gauge_repr_extra__(self, gauge, at=None):
        pass

    def __repr__(self):
        return '<{0} {1}/{2}s>'.format(type(self).__name__, *self)


class Linear(Momentum):

    pass


class Discrete(Momentum):

    normalize_ticks = int

    def move_in(self, gauge, at=None):
        at = now_or(at)
        if self.effects(gauge, at):
            timedelta = gauge.time_passed(at)
            return self.interval - (timedelta.total_seconds() % self.interval)
