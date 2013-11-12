# -*- coding: utf-8 -*-
from collections import namedtuple
from datetime import datetime
import math


__all__ = ['Gravity', 'Linear', 'Discrete']


class Gravity(namedtuple('Gravity', ['delta', 'interval'])):

    normalize_ticks = lambda x: x

    def applies(self, gauge, at=None):
        """Weather this gravity is applying to the gauge."""
        current = gauge.current(at)
        return current < gauge.max if self.delta > 0 else current > gauge.min

    def limit(self, gauge, value):
        if self.delta > 0:
            return min(value, -gauge.delta)
        else:
            return max(value, -gauge.delta)

    def __gauge_repr_extra__(self, gauge, at=None):
        pass

    def __repr__(self):
        return '<{0} {1}/{2}s>'.format(type(self).__name__, *self)


class Linear(Gravity):

    pass


class Discrete(Gravity):

    normalize_ticks = int

    def apply_in(self, gauge, at=None):
        at = at or datetime.utcnow()
        if self.applies(gauge, at):
            timedelta = gauge.time_passed(at)
            return self.interval - (timedelta.total_seconds() % self.interval)

    def __gauge_repr_extra__(self, gauge, at=None):
        apply_in = self.apply_in(gauge, at)
        if apply_in is None:
            return
        sign = '+' if self.delta > 0 else ''
        seconds = math.ceil(apply_in)
        return  '{0}{1} in {2} sec'.format(sign, self.delta, seconds)
