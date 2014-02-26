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
__version__ = '0.0.3'


add = 1
remove = 0
inf = float('inf')


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

    def __init__(self, value, min=0, max=10, at=None):
        self.min = min
        self.max = max
        self.value = value
        self.set_at = now_or(at)
        self.momenta = sortedlist(key=indexer(2))
        self.plan = sortedlist(key=indexer(0))

    @property
    def determination(self):
        """Returns the cached determination. If there's no the cache, it
        determines and caches that.

        A determination is a sorted list of 2-dimensional points which take
        times as x-values, gauge values as y-values.
        """
        try:
            return self._determination
        except AttributeError:
            self._determination = self.determine()
            return self._determination

    @determination.deleter
    def determination(self):
        """Clears the cached determination. If you touches the determination
        at the next first time, that will be redetermined.
        """
        try:
            del self._determination
        except AttributeError:
            pass

    def _current_value_and_velocity(self, at=None):
        at = now_or(at)
        x = self.determination.bisect_left((at,))
        if x == 0:
            return (self.determination[0][1], 0.)
        try:
            next_time, next_value = self.determination[x]
        except IndexError:
            return (self.determination[-1][1], 0.)
        prev_time, prev_value = self.determination[x - 1]
        t = float(at - prev_time) / (next_time - prev_time)
        delta = next_value - prev_value
        value = prev_value + t * delta
        velocity = delta / (next_time - prev_time)
        return (value, velocity)

    def current(self, at=None):
        """Predicts the current value.

        :param at: the time to observe. (default: now)
        """
        return self._current_value_and_velocity(at)[0]

    def velocity(self, at=None):
        """Predicts the current velocity.

        :param at: the time to observe. (default: now)
        """
        return self._current_value_and_velocity(at)[1]

    def incr(self, delta, limit=True, at=None):
        """Increases the value by the given delta immediately. The
        determination would be changed.

        :param delta: the value to increase.
        :param limit: checks if the value is in the range. (default: ``True``)
        :param at: the time to increase. (default: now)

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
        """Decreases the value by the given delta immediately. The
        determination would be changed.

        :param delta: the value to decrease.
        :param limit: checks if the value is in the range. (default: ``True``)
        :param at: the time to decrease. (default: now)

        :raises ValueError: the value is out of the range.
        """
        return self.incr(-delta, limit, at)

    def set(self, value, limit=True, at=None):
        """Sets the current value immediately. The determination would be
        changed.

        :param value: the value to set.
        :param limit: checks if the value is in the range. (default: ``True``)
        :param at: the time to set. (default: now)

        :raises ValueError: the value is out of the range.
        """
        at = now_or(at)
        return self.incr(value - self.current(at), limit, at)

    def add_momentum(self, velocity_or_momentum, since=None, until=None):
        """Adds a momentum. A momentum includes the velocity and the times to
        start to affect and to stop to affect. The determination would be
        changed.

        :param velocity_or_momentum: a :class:`Momentum` object or just a
                                     number for the velocity.
        :param since: if the first argument is a velocity, it is the time to
                      start to affect the momentum. (default: ``None``)
        :param until: if the first argument is a velocity, it is the time to
                      finish to affect the momentum. (default: ``None``)

        :returns: a momentum object. Use this to remove the momentum by
                  :meth:`remove_momentum`.
        """
        if isinstance(velocity_or_momentum, Momentum):
            assert since is until is None
            momentum = velocity_or_momentum
        else:
            momentum = Momentum(velocity_or_momentum, since, until)
        self.momenta.add(momentum)
        self.plan.add((since, add, momentum))
        if until is not None:
            self.plan.add((until, remove, momentum))
        del self.determination
        return momentum

    def remove_momentum(self, momentum):
        """Removes the given momentum. The determination would be changed.

        :param momentum: the :class:`Momentum` object to remove.
        """
        self.momenta.remove(momentum)
        del self.determination

    def forget_past(self, value=None, at=None):
        """Discards the momenta which doesn't effect anymore.

        :param value: the value to set coercively.
        :param at: the time base. (default: now)
        """
        at = now_or(at)
        if value is None:
            value = self.current(at)
        self.value = value
        self.set_at = at
        # forget past momenta
        start = self.momenta.bisect_right(Momentum(0, until=None))
        stop = self.momenta.bisect_left(Momentum(0, until=at))
        del self.momenta[start:stop]
        del self.determination

    def determine(self):
        """Determines the transformations from the time when the value set to
        the farthest future.

        :returns: a sorted list of the determination.
        """
        determination = sortedlist(key=indexer(0))
        # accumulated velocities and the sum of velocities
        velocities = []
        total_velocity = 0
        # variables not set
        method = None
        span = None
        # default
        time = self.set_at
        value = self.value
        # functions
        deter = lambda time, value: determination.add((time, value))
        time_to_reach = lambda goal: (goal - value) / total_velocity
        # trivial variables
        x = 0
        while True:
            if span is None:
                # skip the first loop
                pass
            else:
                # calculate the change
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
                    d = time_to_reach(limit)
                    if 0 < d < span:
                        span -= d
                        prev_time += d
                        value = limit
                        deter(prev_time, value)
                        total_velocity = sum(velocities)
                new_value = value + total_velocity * span
                if new_value > self.max and total_velocity > 0:
                    limit = self.max
                elif new_value < self.min and total_velocity < 0:
                    limit = self.min
                else:
                    limit = None
                if limit is None:
                    value = new_value
                else:
                    # the new value is out of the range
                    d = time_to_reach(limit)
                    if 0 < d:
                        value = limit
                        deter(prev_time + d, value)
            if span == inf:
                # the final loop
                break
            elif span is None or span:
                # determine the current point
                deter(time, value)
            # apply the current plan
            if method == add:
                velocities.append(momentum.velocity)
            elif method == remove:
                velocities.remove(momentum.velocity)
            # prepare the next iteration
            prev_time = time
            try:
                time, method, momentum = self.plan[x]
            except IndexError:
                span = inf
                continue
            if momentum not in self.momenta:
                del self.plan[x]
                continue
            # normalize time
            if time is None:
                time = self.set_at
            else:
                time = float(max(self.set_at, time))
            span = time - prev_time
            x += 1
        return determination

    def __repr__(self, at=None):
        at = now_or(at)
        current = self.current(at)
        if self.min == 0:
            fmt = '<{0} {1:.2f}/{2}>'
        else:
            fmt = '<{0} {1:.2f}>'
        return fmt.format(type(self).__name__, current, self.max)


class Momentum(namedtuple('Momentum', ['velocity', 'since', 'until'])):
    """A power of which increases or decreases the gauge continually between a
    specific period.
    """

    def __new__(cls, velocity, since=None, until=None):
        velocity = float(velocity)
        return super(Momentum, cls).__new__(cls, velocity, since, until)

    def __repr__(self):
        string = '<{0} {1:+.2f}/s'.format(type(self).__name__, self.velocity)
        if self.since is not None or self.until is not None:
            string += ' {0}~{1}'.format(
                '' if self.since is None else self.since,
                '' if self.until is None else self.until)
        string += '>'
        return string
