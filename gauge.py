# -*- coding: utf-8 -*-
"""
    gauge
    ~~~~~

    Deterministic gauge library.

    :copyright: (c) 2013-2014 by Heungsub Lee
    :license: BSD, see LICENSE for more details.
"""
from datetime import datetime

from blist import sortedlist


POSITIVE = 0
NEGATIVE = 1
epoch = datetime.fromtimestamp(0)
ADD = 1
SUB = 0


def now_or(at):
    return datetime.utcnow() if at is None else at


def sort_key(tup):
    return None if tup[0] is None else tup[0].timetuple()


class Gauge(object):

    min = None
    max = None
    value = 0
    set_at = None
    momenta = None
    events = None

    def __init__(self, value, min=0, max=10, at=None):
        self.min = min
        self.max = max
        self.value = value
        self.set_at = now_or(at)
        self.momenta = sortedlist(key=sort_key)
        self.events = sortedlist(key=sort_key)

    def inertia(self, velocity, since=None, until=None):
        self.momenta.add((since, until, velocity))
        self.events.add((since, ADD, velocity))
        if until is not None:
            self.events.add((until, SUB, velocity))

    def calc(self, alpha, velocities, duration):
        value = alpha + sum(velocities) * duration.total_seconds()
        return float(min(self.max, max(self.min, value)))

    def current(self, at=None):
        at = now_or(at)
        alpha = self.value
        velocities = []
        prev_time = None
        for time, method, velocity in self.events:
            if time is None:
                time = self.set_at
            if at < time:
                time = prev_time or self.set_at
                break
            if prev_time is not None:
                alpha = self.calc(alpha, velocities, time - prev_time)
            if method == ADD:
                velocities.append(velocity)
            elif method == SUB:
                velocities.remove(velocity)
            prev_time = time
        return self.calc(alpha, velocities, at - time)

    def velocity(self, at=None):
        at = now_or(at)
        velocities = []
        for time, method, velocity in self.events:
            if at < (time or self.set_at):
                break
            if method == ADD:
                velocities.append(velocity)
            elif method == SUB:
                velocities.remove(velocity)
        return sum(velocities)

    def incr(self, delta, limit=True, at=None):
        at = now_or(at)
        self.value = self.current(at) + delta
        self.set_at = at
        start = self.momenta.bisect_right((None,))
        stop = self.momenta.bisect_left((at,))
        del self.momenta[start:stop]
        start = self.events.bisect_right((None,))
        stop = self.events.bisect_left((at,))
        del self.events[start:stop]

    def decr(self, delta, limit=True, at=None):
        """Decreases the value by the given delta."""
        return self.incr(-delta, limit, at)

    def set(self, value, limit=True, at=None):
        at = now_or(at)
        return self.incr(value - self.current(at), limit, at)
