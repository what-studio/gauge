# -*- coding: utf-8 -*-
"""
    gauge
    ~~~~~

    Deterministic linear gauge library.

    :copyright: (c) 2013-2014 by Heungsub Lee
    :license: BSD, see LICENSE for more details.
"""
from collections import namedtuple
import time

from blist import sortedlist


__all__ = ['Gauge', 'Momentum']
__version__ = '0.0.1'


ADD = 1
REMOVE = 0


def now_or(at):
    return time.time() if at is None else float(at)


def indexer(x):
    return lambda v: v[x]


class Gauge(object):

    min = None
    max = None
    value = 0
    set_at = None

    momenta = None
    plan = None
    determination = None

    def __init__(self, value, min=0, max=10, at=None):
        self.min = min
        self.max = max
        self.value = value
        self.set_at = now_or(at)
        self.momenta = sortedlist(key=indexer(2))
        self.plan = sortedlist(key=indexer(0))

    def add_momentum(self, velocity_or_momentum, since=None, until=None):
        """Adds a momentum. A momentum includes the velocity and the times to
        start to affect and to stop to affect.

        :returns: a momentum object. Use this to remove the momentum by
                  :meth:`remove_momentum`.
        """
        if isinstance(velocity_or_momentum, Momentum):
            assert since is until is None
            momentum = velocity_or_momentum
        else:
            momentum = Momentum(velocity_or_momentum, since, until)
        self.momenta.add(momentum)
        self.plan.add((since, ADD, momentum))
        if until is not None:
            self.plan.add((until, REMOVE, momentum))
        self.determination = self.determine()
        return momentum

    def remove_momentum(self, momentum):
        self.momenta.remove(momentum)
        self.determination = self.determine()

    def forget_past(self, value=None, at=None):
        at = now_or(at)
        if value is None:
            value = self.current(at)
        self.value = value
        self.set_at = at
        # forget past momenta
        start = self.momenta.bisect_right(Momentum(0))
        stop = self.momenta.bisect_left(Momentum(0, until=at))
        del self.momenta[start:stop]
        self.determination = self.determine()

    def determine(self):
        determination = sortedlist(key=indexer(0))
        velocities = []
        prev_time = None
        x = 0
        total_velocity = 0
        while True:
            try:
                time, method, momentum = self.plan[x]
            except IndexError:
                break
            if momentum not in self.momenta:
                del self.plan[x]
                # don't increase x
                continue
            # normalize time
            if time is None:
                time = self.set_at
            else:
                time = float(max(self.set_at, time))
            if x == 0:
                # at the first effective plan
                value = self.value
                determination.add((time, value))
            elif time != prev_time:
                span = time - prev_time
                if value > self.max:
                    limit = self.max
                    total_velocity = sum(v for v in velocities if v < 0)
                elif value < self.min:
                    limit = self.min
                    total_velocity = sum(v for v in velocities if v > 0)
                else:
                    limit = None
                    total_velocity = sum(velocities)
                if limit is not None and total_velocity != 0:
                    # the previous value is out of the range
                    d = (limit - value) / total_velocity
                    if d < span:
                        determination.add((prev_time + d, limit))
                        value = limit
                        span -= d
                        total_velocity = sum(velocities)
                new_value = value + total_velocity * span
                if new_value > self.max and total_velocity > 0:
                    limit = self.max
                elif new_value < self.min and total_velocity < 0:
                    limit = self.min
                else:
                    limit = None
                if limit is not None:
                    # the new value is out of the range
                    d = (limit - value) / total_velocity
                    determination.add((prev_time + d, limit))
                    value = limit
                else:
                    value = new_value
                determination.add((time, value))
            # prepare next plan
            if method == ADD:
                velocities.append(momentum.velocity)
            elif method == REMOVE:
                velocities.remove(momentum.velocity)
            prev_time = time
            x += 1
        # have an infinite momentum
        total_velocity = sum(velocities)
        if value < self.max and total_velocity > 0:
            limit = self.max
        elif value > self.min and total_velocity < 0:
            limit = self.min
        else:
            limit = None
        if limit is not None:
            d = (limit - value) / total_velocity
            determination.add((prev_time + d, limit))
        return determination

    def current(self, at=None, debug=False):
        """Calculates the current value.

        :param at: the datetime. (default: now)
        """
        if not self.determination:
            return self.value
        at = now_or(at)
        x = self.determination.bisect_left((at,))
        if x == 0:
            return self.determination[0][1]
        try:
            next_time, next_value = self.determination[x]
        except IndexError:
            return self.determination[-1][1]
        prev_time, prev_value = self.determination[x - 1]
        t = float(at - prev_time) / (next_time - prev_time)
        value = prev_value + t * (next_value - prev_value)
        return value

    def velocity(self, at=None):
        if not self.determination:
            return 0
        at = now_or(at)
        x = self.determination.bisect_left((at,))
        if x == 0:
            return 0
        try:
            next_time, next_value = self.determination[x]
        except IndexError:
            return 0
        prev_time, prev_value = self.determination[x - 1]
        return (next_value - prev_value) / (next_time - prev_time)

    def incr(self, delta, limit=True, at=None):
        """Increases the value by the given delta.

        :param delta: the value to increase.
        :param limit: checks if the value is in the range. (default: ``True``)
        :param at: the datetime. (default: now)

        :raises ValueError: the value is out of the range.
        """
        at = now_or(at)
        value = self.current(at) + delta
        if limit:
            if delta > 0 and value > self.max:
                raise ValueError(
                    'The value to set is over the maximum ({0} > {1})'
                    ''.format(value, self.max))
            elif delta < 0 and value < self.min:
                raise ValueError(
                    'The value to set is under the minimum ({0} < {1})'
                    ''.format(value, self.min))
        self.forget_past(value, at)
        return value

    def decr(self, delta, limit=True, at=None):
        """Decreases the value by the given delta.

        :param delta: the value to decrease.
        :param limit: checks if the value is in the range. (default: ``True``)
        :param at: the datetime. (default: now)

        :raises ValueError: the value is out of the range.
        """
        return self.incr(-delta, limit, at)

    def set(self, value, limit=True, at=None):
        at = now_or(at)
        return self.incr(value - self.current(at), limit, at)

    def __repr__(self, at=None):
        at = now_or(at)
        current = self.current(at)
        if self.min == 0:
            fmt = '<{0} {1}/{2}>'
        else:
            fmt = '<{0} {1}>'
        return fmt.format(type(self).__name__, current, self.max)


class Momentum(namedtuple('Momentum', ['velocity', 'since', 'until'])):

    def __new__(cls, velocity, since=None, until=None):
        return super(Momentum, cls).__new__(cls, velocity, since, until)

    def __init__(self, velocity, since=None, until=None):
        return super(Momentum, self).__init__(velocity, since, until)
