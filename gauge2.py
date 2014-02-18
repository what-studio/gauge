# -*- coding: utf-8 -*-
"""
    gauge
    ~~~~~

    Deterministic gauge library.

    :copyright: (c) 2013-2014 by Heungsub Lee
    :license: BSD, see LICENSE for more details.
"""
from collections import namedtuple
from datetime import datetime

from blist import sortedlist


POSITIVE = 0
NEGATIVE = 1


def now_or(at):
    return datetime.utcnow() if at is None else at


def sort_key((momentum, since, until)):
    return None if since is None else since.timetuple()


class Gauge(object):

    max = None
    min = None
    default_momentum = None
    value_type = float

    delta = 0
    set_at = None

    def __init__(self, value, limit=True, at=None):
        if value is None:
            value = self.max
        #self.set(value, limit, at)
        self.delta = value
        self.set_at = now_or(at)
        self.momenta = sortedlist(key=sort_key)
        if self.default_momentum is not None:
            self.add_momentum(self.default_momentum)

    def add_momentum(self, momentum, since=None, until=None, at=None):
        at = now_or(at)
        current = self.current(at)
        self.trim_momenta(at)
        #if not self.min < current < self.max:
        self.set(current, limit=False, at=at)
        self.momenta.add((momentum, since, until))

    def trim_momenta(self, at=None):
        at = now_or(at)
        for x, (momentum, since, until) in enumerate(self.momenta):
            if until is not None and until < at:
                del self.momenta[x]

    def speed(self, at=None):
        at = now_or(at)
        speed = 0.0
        for momentum, since, until in self.momenta:
            future = since is not None and at < since
            past = until is not None and at > until
            if future or past:
                continue
            speed += momentum.speed()
        return speed

    def set(self, value, limit=True, at=None):
        """Sets as the given value.

        :param value: the value to set.
        :param limit: checks if the value is in the range. Defaults to
                      ``True``.
        :param at: the datetime. Defaults to now.
        """
        at = now_or(at)
        return self.incr(value - self.current(at), limit, at)

    def incr(self, delta, limit=True, at=None):
        """Increases the value by the given delta.

        :param delta: the value to set.
        :param limit: checks if the value is in the range. Defaults to
                      ``True``.
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
        pos, neg = False, False
        for momentum, since, until in self.momenta:
            future = since is not None and at < since
            past = until is not None and at > until
            if future or past:
                continue
            if momentum.delta > 0:
                pos = True
            else:
                neg = True
        if current <= self.min and not pos or current >= self.max and not neg:
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
        return self.value_type(self.delta + self.delta_moved(at))

    def delta_moved(self, at=None):
        """The delta moved by the momenta."""
        pos_delta, pos_limit, neg_delta, neg_limit = self.stuffs(at)
        return min(pos_delta, pos_limit) + max(neg_delta, neg_limit)

    def real_current(self, at=None):
        pos_delta, pos_limit, neg_delta, neg_limit = self.stuffs(at)
        return self.value_type(self.delta + pos_delta + neg_delta)

    def stuffs(self, at=None):
        at = now_or(at)
        #seconds = self.time_passed(at).total_seconds()
        pos_deltas = []
        neg_deltas = []
        for momentum, since, until in self.momenta:
            since = self.set_at if since is None else max(since, self.set_at)
            until = at if until is None else min(until, at)
            if until < since:
                continue
            seconds_passed = (until - since).total_seconds()
            delta = momentum.move(self, seconds_passed)
            (pos_deltas if momentum.delta > 0 else neg_deltas).append(delta)
        pos_delta = sum(pos_deltas)
        neg_delta = sum(neg_deltas)
        pos_limit = max(self.max - self.delta - neg_delta, 0)
        neg_limit = min(self.min - self.delta - pos_delta, 0)
        return (pos_delta, pos_limit, neg_delta, neg_limit)

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
        if self.min == 0:
            fmt = '<{0} {1}/{2}>'
        else:
            fmt = '<{0} {1}>'
        return fmt.format(type(self).__name__, current, self.max)


class Momentum(namedtuple('Momentum', ['delta', 'interval'])):

    normalize_ticks = float

    def speed(self):
        return self.delta / self.interval

    def effects(self, gauge, at=None):
        """Weather this momentum is applying to the gauge."""
        current = gauge.current(at)
        if self.delta > 0:
            return current < gauge.max
        else:
            return current > gauge.min

    def move(self, gauge, seconds):
        ticks = self.normalize_ticks(seconds / self.interval)
        delta = self.delta * ticks
        return delta

    def limit(self, gauge, value):
        if self.delta > 0:
            return min(gauge.max - gauge.delta, value)
        else:
            return max(gauge.min - gauge.delta, value)

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
