# -*- coding: utf-8 -*-
from __future__ import absolute_import
from datetime import datetime

from .gravity import Discrete, Gravity, Linear


def now_or(at):
    return datetime.utcnow() if at is None else at


class Gauge(object):

    min = None
    max = None
    default_gravity = None
    value_type = float

    delta = 0
    set_at = None

    def __init__(self, value, limit=True, at=None):
        if value is None:
            value = self.max
        #self.set(value, limit, at)
        self.delta = value
        self.set_at = now_or(at)
        self.gravities = []
        if self.default_gravity is not None:
            self.add_gravity(self.default_gravity)

    def add_gravity(self, gravity):
        self.gravities.append(gravity)

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
            if delta > 0 and next > self.max:
                raise ValueError('The value to set is over the maximum')
            elif delta < 0 and next < self.min:
                raise ValueError('The value to set is under the minimum')
        if not self.min < current < self.max:
            # go to be gravitated
            self.set_at = at
            self.delta = next
        else:
            self.delta += delta
        print next, self.set_at, self.delta

    def decr(self, delta, limit=True, at=None):
        """Decreases the value by the given delta."""
        return self.incr(-delta, limit, at)

    def current(self, at=None):
        """Calculates the current value."""
        print self.delta, self.delta_gravitated(at)
        return self.value_type(self.delta + self.delta_gravitated(at))

    def delta_gravitated(self, at=None):
        """The delta moved by the gravities."""
        timedelta = self.time_passed(at)
        if timedelta is None:
            return 0
        seconds = timedelta.total_seconds()
        pos_deltas = []
        neg_deltas = []
        for gravity in self.gravities:
            delta = gravity.delta_gravitated(self, seconds)
            (pos_deltas if delta > 0 else neg_deltas).append(delta)
        pos_delta = sum(pos_deltas)
        neg_delta = sum(neg_deltas)
        print pos_delta, neg_delta
        #print min(max(self.min, self.max - self.delta - neg_delta), pos_delta),\
        #      max(min(self.max, self.min - self.delta - pos_delta), neg_delta)
        return (
            min(max(self.min, self.max - self.delta - neg_delta), pos_delta) +
            max(min(self.max, self.min - self.delta - pos_delta), neg_delta))

    def time_passed(self, at=None):
        """The timedelta object passed from :attr:`set_at`."""
        if self.set_at is None:
            return None
        at = at or datetime.utcnow()
        return at - self.set_at

    def __eq__(self, other, at=None):
        if isinstance(other, type(self)):
            return self.__getstate__() == other.__getstate__()
        elif isinstance(other, (int, float)):
            return float(self.current(at)) == other
        return False

    def __repr__(self, at=None):
        at = at or datetime.utcnow()
        current = self.current(at)
        rv = '<%s %d/%d' % (type(self).__name__, current, self.max)
        try:
            extra = self.gravity.__gauge_repr_extra__(self, at)
        except AttributeError:
            pass
        else:
            if extra is not None:
                rv += ' ({})'.format(extra)
        return rv + '>'
