# -*- coding: utf-8 -*-
from collections import namedtuple
from datetime import datetime
import math


class Gauge(object):

    min = None
    max = None
    base = None
    gravity = None

    delta = None
    set_at = None

    def __init__(self, value=None):
        if value is None:
            value = self.max
        self.set(value)

    def set(self, value, limit=True, at=None):
        self.delta = value - self.base
        self.set_at = None
        if value < self.base:
            self.incr(value - self.current(at))

    def incr(self, delta, limit=True, at=None):
        at = at or datetime.utcnow()
        current = self.current(at)
        next = current + delta
        if limit and next > self.base:
            raise ValueError()
        if next < self.base <= current:
            self.delta = next - self.base
            self.set_at = at
        elif next > self.base:
            self.delta = next - self.base
            self.set_at = None
        else:
            self.delta += next - current

    def decr(self, delta, limit=True, at=None):
        return self.incr(-delta, limit, at)

    def current(self, at=None):
        return self.base + self.delta + self.delta_by_gravity(at)

    def time_passed(self, at=None):
        if self.set_at is None:
            return None
        at = at or datetime.utcnow()
        return (at - self.set_at).total_seconds()

    def ticks_passed(self, at=None):
        time = self.time_passed(at)
        if time is None:
            return None
        return time / self.gravity.interval

    def delta_by_gravity(self, at=None):
        ticks = self.ticks_passed(at)
        if ticks is None:
            return 0
        normalized_ticks = self.gravity.normalize_ticks(ticks)
        return min(self.gravity.delta * normalized_ticks, -self.delta)

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
        extra = self.gravity.__gauge_repr_extra__(self, at)
        if extra is not None:
            rv += ' ({})'.format(extra)
        return rv + '>'


class Gravity(namedtuple('Gravity', ['delta', 'interval'])):

    def normalize_ticks(self, ticks):
        return ticks

    def __repr__(self):
        return '<{0} {1}/{2}s>'.format(type(self).__name__, *self)


class Linear(Gravity):

    pass


class Stairs(Gravity):

    normalize_ticks = int

    def apply_in(self, gauge, at=None):
        at = at or datetime.utcnow()
        if gauge.current(at) >= gauge.max:
            return
        time = gauge.time_passed(at)
        return self.interval - (time % self.interval)

    def __gauge_repr_extra__(self, gauge, at=None):
        apply_in = self.apply_in(gauge, at)
        if apply_in is not None:
            return  '+{0} in {1} sec'.format(self.delta, math.ceil(apply_in))
