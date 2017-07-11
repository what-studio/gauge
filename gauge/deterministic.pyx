# -*- coding: utf-8 -*-
"""
   gauge.deterministic
   ~~~~~~~~~~~~~~~~~~~

   Determining logics for gauge.

   :copyright: (c) 2013-2017 by What! Studio
   :license: BSD, see LICENSE for more details.

"""
from __future__ import absolute_import

import math
import operator

from gauge.common import ADD, inf, now_or, REMOVE, TIME, VALUE
from gauge.gauge cimport Gauge, Momentum


__all__ = ['Determination', 'Line', 'Horizon', 'Ray', 'Segment', 'Boundary']


cdef list value_lines(Gauge gauge, double value):
    return [Horizon(gauge._base_time, +inf, value)]


cdef list gauge_lines(Gauge gauge, Gauge other_gauge):
    cdef list lines = []
    cdef Determination determination = other_gauge.determination
    first, last = determination[0], determination[-1]
    if gauge._base_time < first[TIME]:
        lines.append(Horizon(gauge._base_time, first[TIME], first[VALUE]))
    zipped_determination = zip(determination[:-1], determination[1:])
    for (time1, value1), (time2, value2) in zipped_determination:
        lines.append(Segment(time1, time2, value1, value2))
    lines.append(Horizon(last[TIME], +inf, last[VALUE]))
    return lines


cdef class Determination(list):
    """Determination of a gauge is a list of `(time, value)` pairs.

    :param determining: a :meth:`Gauge.determine` iterator.

    """

    @property
    def in_range_since(self):
        if self._in_range:
            return self._in_range_since

    cdef void _determine(self, double time, double value, bint in_range=True):
        if self and self[-1][TIME] == time:
            return
        if in_range and not self._in_range:
            self._in_range = True
            self._in_range_since = time
        self.append((time, value))

    def __init__(self, Gauge gauge):
        """Determines the transformations from the time when the value set to
        the farthest future.
        """
        cdef double since
        cdef double until
        cdef double value
        cdef double velocity = 0
        cdef list velocities = []
        since, value = gauge._base_time, gauge._base_value
        self._in_range = False
        # boundaries.
        cdef list ceil_lines
        cdef list floor_lines
        if gauge._max_gauge is None:
            ceil_lines = value_lines(gauge, gauge._max_value)
        else:
            ceil_lines = gauge_lines(gauge, gauge._max_gauge)
        if gauge._min_gauge is None:
            floor_lines = value_lines(gauge, gauge._min_value)
        else:
            floor_lines = gauge_lines(gauge, gauge._min_gauge)

        cdef Boundary bound
        cdef Boundary boundary
        cdef ceil = Boundary(ceil_lines, operator.lt)
        cdef floor = Boundary(floor_lines, operator.gt)
        cdef boundaries = [ceil, floor]
        cdef bint bounded = False
        cdef bint overlapped = False
        for boundary in boundaries:
            # skip past boundaries.
            while boundary.line.until <= since:
                boundary._walk()
            # check overflowing.
            if bounded:
                continue
            boundary_value = boundary.line.guess(since)
            if boundary.cmp(boundary_value, value):
                bound, bounded, overlapped = boundary, True, False
        cdef double time
        cdef int method
        cdef Momentum momentum
        cdef bint again
        cdef list walked_boundaries
        cdef Boundary b
        for time, method, momentum in gauge.momentum_events():
            # normalize time.
            until = max(time, gauge._base_time)
            # if True, An iteration doesn't choose next boundaries.  The first
            # iteration doesn't require to choose next boundaries.
            again = True
            while since < until:
                if again:
                    again = False
                    if bounded:
                        walked_boundaries = [bound]
                    else:
                        walked_boundaries = boundaries
                else:
                    # stop the loop if all boundaries have been proceeded.
                    # if all(b.line.until >= until for b in boundaries):
                    #     break
                    for b in boundaries:
                        if b.line.until < until:
                            break
                    else:
                        break
                    # ---
                    # choose the next boundary.
                    # boundary = min(boundaries, key=lambda b: b.line.until)
                    boundary = boundaries[0]
                    for b in boundaries:
                        if b.line.until < boundary.line.until:
                            boundary = b
                    # ---
                    boundary._walk()
                    walked_boundaries = [boundary]
                # calculate velocity.
                if not bounded:
                    velocity = sum(velocities)
                elif overlapped:
                    velocity = bound.best(sum(velocities), bound.line.velocity)
                else:
                    velocity = sum(v for v in velocities if bound.cmp(v, 0))
                # is still bound?
                if overlapped and bound.cmp(velocity, bound.line.velocity):
                    bounded, overlapped = False, False
                    again = True
                    continue
                # current value line.
                line = Ray(since, until, value, velocity)
                if overlapped:
                    bound_until = min(bound.line.until, until)
                    if bound_until == +inf:
                        break
                    # released from the boundary.
                    since, value = (bound_until, bound.line.get(bound_until))
                    self._determine(since, value)
                    continue
                for boundary in walked_boundaries:
                    # find the intersection with a boundary.
                    try:
                        intersection = line.intersect(boundary.line)
                    except ValueError:
                        continue
                    if intersection[TIME] == since:
                        continue
                    again = True  # iterate with same boundaries again.
                    bound, bounded, overlapped = boundary, True, True
                    since, value = intersection
                    # clamp by the boundary.
                    value = boundary.best(value, boundary.line.guess(since))
                    self._determine(since, value)
                    break
                if bounded:
                    continue  # the intersection was found.
                for boundary in walked_boundaries:
                    # find missing intersection caused by floating-point
                    # inaccuracy.
                    bound_until = min(boundary.line.until, until)
                    if bound_until == +inf or bound_until < since:
                        continue
                    boundary_value = boundary.line.get(bound_until)
                    if boundary.cmp_eq(line.get(bound_until), boundary_value):
                        continue
                    bound, bounded, overlapped = boundary, True, True
                    since, value = bound_until, boundary_value
                    self._determine(since, value)
                    break
            if until == +inf:
                break
            # determine the final node in the current itreration.
            value += velocity * (until - since)
            self._determine(until, value, in_range=not bounded or overlapped)
            # prepare the next iteration.
            if method == ADD:
                velocities.append(momentum.velocity)
            elif method == REMOVE:
                velocities.remove(momentum.velocity)
            since = until


class Line(object):
    """An abstract class to represent lines between 2 times which start from
    `value`.  Subclasses should describe where lines end.

    .. note::

       Each subclass must implement :meth:`_get`, :meth:`_earlier`,
       :meth:`_later`, and :attr:`velocity` property.

    """

    __slots__ = ('since', 'until', 'value')

    velocity = NotImplemented

    def __init__(self, since, until, value):
        self.since = since
        self.until = until
        self.value = value

    def get(self, at=None):
        """Returns the value at the given time.

        :raises ValueError: the given time is out of the time range.
        """
        at = now_or(at)
        if not self.since <= at <= self.until:
            raise ValueError('Out of the time range: {0:.2f}~{1:.2f}'
                             ''.format(self.since, self.until))
        return self._get(at)

    def guess(self, at=None):
        """Returns the value at the given time even the time it out of the time
        range.
        """
        at = now_or(at)
        if at < self.since:
            return self._earlier(at)
        elif at > self.until:
            return self._later(at)
        else:
            return self.get(at)

    def _get(self, double at):
        """Implement at subclass as to calculate the value at the given time
        which is between the time range.
        """
        raise NotImplementedError

    def _earlier(self, double at):
        """Implement at subclass as to calculate the value at the given time
        which is earlier than `since`.
        """
        raise NotImplementedError

    def _later(self, double at):
        """Implement at subclass as to calculate the value at the given time
        which is later than `until`.
        """
        raise NotImplementedError

    def intersect(self, line):
        """Gets the intersection with the given line.

        :raises ValueError: there's no intersection.
        """
        cdef double time
        cdef double value
        lines = [self, line]
        lines.sort(key=intersection_reliability, reverse=True)
        left, right = lines  # right is more reliable.
        if math.isinf(right.velocity):
            # right is almost vertical.
            time = (right.since + right.until) / 2
        else:
            velocity_delta = left.velocity - right.velocity
            if velocity_delta == 0:
                raise ValueError('Parallel line given')
            intercept_delta = right.intercept() - left.intercept()
            time = intercept_delta / velocity_delta
        since = max(left.since, right.since)
        until = min(left.until, right.until)
        if not since <= time <= until:
            raise ValueError('Intersection not in the time range')
        value = left.get(time)
        return (time, value)

    def intercept(self):
        """Gets the value-intercept. (Y-intercept)"""
        return self.value - self.velocity * self.since

    def _repr(self, str string):
        return ('<{0}{1} for {2!r}~{3!r}>'
                ''.format(type(self).__name__, string, self.since, self.until))

    def __repr__(self):
        return self._repr('')


class Horizon(Line):
    """A line which has no velocity."""

    __slots__ = ('since', 'until', 'value')

    velocity = 0

    def _get(self, double at):
        return self.value

    def _earlier(self, double at):
        return self.value

    def _later(self, double at):
        return self.value

    def __repr__(self):
        return super(Horizon, self)._repr(' {0:.2f}'.format(self.value))


class Ray(Line):
    """A line based on starting value and velocity."""

    __slots__ = ('since', 'until', 'value', 'velocity')

    def __init__(self, since, until, value, velocity):
        super(Ray, self).__init__(since, until, value)
        self.velocity = velocity

    def _get(self, double at):
        return self.value + self.velocity * (at - self.since)

    def _earlier(self, double at):
        return self.value

    def _later(self, double at):
        return self._get(self.until)

    def __repr__(self):
        string = ' {0:.2f}{1:+.2f}/s'.format(self.value, self.velocity)
        return super(Ray, self)._repr(string)


class Segment(Line):
    """A line based on starting and ending value."""

    __slots__ = ('since', 'until', 'value',
                 'final')  # the value at `until`.

    @staticmethod
    def _calc_value(double at,
                    double time1, double time2,
                    double value1, double value2):
        if at == time1:
            return value1
        elif at == time2:
            return value2
        cdef double rate = float(at - time1) / (time2 - time1)
        return value1 + rate * (value2 - value1)

    @staticmethod
    def _calc_velocity(double time1, double time2,
                       double value1, double value2):
        return (value2 - value1) / (time2 - time1)

    @property
    def velocity(self):
        return self._calc_velocity(self.since, self.until,
                                   self.value, self.final)

    def __init__(self, double since, double until, double value, double final):
        super(Segment, self).__init__(since, until, value)
        self.final = final

    def _get(self, double at):
        return self._calc_value(at, self.since, self.until,
                                self.value, self.final)

    def _earlier(self, double at):
        return self.value

    def _later(self, double at):
        return self.final

    def __repr__(self):
        string = ' {0:.2f}~{1:.2f}'.format(self.value, self.final)
        return super(Segment, self)._repr(string)


#: The reliability map of line classes for precise intersection.
_intersection_reliabilities = {Horizon: 3, Ray: 2, Segment: 1}

#: Sorting key to sort by intersection reliability.
intersection_reliability = lambda l: _intersection_reliabilities[type(l)]


cdef class Boundary:

    cdef:
        public line
        public lines_iter
        public cmp
        public best

    def __init__(self, list lines, cmp=operator.lt):
        assert cmp in [operator.lt, operator.gt]
        self.lines_iter = iter(lines)
        self.cmp = cmp
        self.best = {operator.lt: min, operator.gt: max}[cmp]
        self._walk()

    cdef _walk(self):
        """Choose the next line."""
        self.line = next(self.lines_iter)

    cdef bint _cmp_eq(self, double x, double y):
        return x == y or self.cmp(x, y)

    cdef bint _cmp_inv(self, double x, double y):
        return x != y and not self.cmp(x, y)

    def walk(self):
        return self._walk()

    def cmp_eq(self, double x, double y):
        return self._cmp_eq(x, y)

    def cmp_inv(self, double x, double y):
        return self._cmp_inv(x, y)

    def __repr__(self):
        # NOTE: __name__ is 'Boundary' in CPython, but 'deterministic.Boundary'
        # in PyPy.  So here it picks only the last word.
        __, __, name = self.__class__.__name__.rpartition('.')
        return '<{0} line={1}, cmp={2}>'.format(name, self.line, self.cmp)
