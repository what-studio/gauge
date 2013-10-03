# -*- coding: utf-8 -*-
from collections import namedtuple
from datetime import datetime
import math


class Gauge(object):

    min = None
    max = None
    gravity = None

    delta = 0
    set_at = None

    def __init__(self, value=None):
        if value is None:
            value = self.goal()
        self.set(value)

    def goal(self):
        """The goal value. If the gravity has positive delta, it is the maximum
        value. Otherwhise the minimum value.
        """
        return self.max if self.gravity.delta > 0 else self.min

    def incr(self, delta, limit=True, at=None):
        """Increases the value by the given delta.

        :param delta: the value to set.
        :param limit: checks if the value is in the range. Defaults to ``True``.
        :param at: the datetime. Defaults to now.
        """
        at = at or datetime.utcnow()
        current = self.current(at)
        next = current + delta
        if limit and not self.min <= next <= self.max:
            raise ValueError('Out of range')
        if self.gravity.applies(self, next):
            if self.gravity.applies(self, current):
                self.delta += next - current
            else:
                self.delta = next - self.goal()
                self.set_at = at
        else:
            self.delta = next - self.goal()
            self.set_at = None

    def decr(self, delta, limit=True, at=None):
        return self.incr(-delta, limit, at)

    def set(self, value, limit=True, at=None):
        """Sets as the given value.

        :param value: the value to set.
        :param limit: checks if the value is in the range. Defaults to ``True``.
        :param at: the datetime. Defaults to now.
        """
        self.incr(value - self.goal(), limit, at)

    def current(self, at=None):
        return self.goal() + self.delta + self.delta_by_gravity(at)

    def time_passed(self, at=None):
        if self.set_at is None:
            return None
        at = at or datetime.utcnow()
        return at - self.set_at

    def ticks_passed(self, at=None):
        timedelta = self.time_passed(at)
        if timedelta is None:
            return None
        return timedelta.total_seconds() / self.gravity.interval

    def delta_by_gravity(self, at=None):
        ticks = self.ticks_passed(at)
        if ticks is None:
            return 0
        normalized_ticks = self.gravity.normalize_ticks(ticks)
        delta = self.gravity.delta * normalized_ticks
        return self.gravity.limit(self, delta)

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


class Gravity(namedtuple('Gravity', ['delta', 'interval'])):

    def normalize_ticks(self, ticks):
        return ticks

    def applies(self, gauge, value):
        if self.delta > 0:
            return gauge.min <= value < gauge.max
        else:
            return gauge.min < value <= gauge.max

    def limit(self, gauge, value):
        if self.delta > 0:
            return min(value, -gauge.delta)
        else:
            return max(value, -gauge.delta)

    def __repr__(self):
        return '<{0} {1}/{2}s>'.format(type(self).__name__, *self)


class Linear(Gravity):

    pass


class Stairs(Gravity):

    normalize_ticks = int

    def apply_in(self, gauge, at=None):
        at = at or datetime.utcnow()
        if not gauge.gravity.applies(gauge, gauge.current(at)):
            return
        timedelta = gauge.time_passed(at)
        return self.interval - (timedelta.total_seconds() % self.interval)

    def __gauge_repr_extra__(self, gauge, at=None):
        apply_in = self.apply_in(gauge, at)
        if apply_in is not None:
            return  '{0}{1} in {2} sec'.format(
                '+' if self.delta > 0 else '', self.delta, math.ceil(apply_in))
