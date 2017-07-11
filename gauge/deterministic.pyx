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

from gauge.common import ADD, inf, REMOVE, TIME, VALUE
from gauge.deterministic cimport SEGMENT_VALUE, SEGMENT_VELOCITY
from gauge.gauge cimport Gauge, Momentum


__all__ = ['Determination', 'Line', 'Horizon', 'Ray', 'Segment', 'Boundary']


# line types:
DEF HORIZON = 1
DEF RAY = 2
DEF SEGMENT = 3


cdef inline list VALUE_LINES(Gauge gauge, double value):
    return [Line(HORIZON, gauge._base_time, +inf, value)]


cdef inline list GAUGE_LINES(Gauge gauge, Gauge other_gauge):
    cdef:
        Line line
        list lines = []
        Determination determination = other_gauge.determination
    first, last = determination[0], determination[-1]
    if gauge._base_time < first[TIME]:
        line = Line(HORIZON, gauge._base_time, first[TIME], first[VALUE])
        lines.append(line)
    zipped_determination = zip(determination[:-1], determination[1:])
    for (time1, value1), (time2, value2) in zipped_determination:
        line = Line(SEGMENT, time1, time2, value1, value2)
        lines.append(line)
    line = Line(HORIZON, last[TIME], +inf, last[VALUE])
    lines.append(line)
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
        cdef:
            double since
            double until
            double value
            double velocity = 0
            list velocities = []
            double boundary_value
        since, value = gauge._base_time, gauge._base_value
        self._in_range = False
        # boundaries.
        cdef list ceil_lines, floor_lines
        if gauge._max_gauge is None:
            ceil_lines = VALUE_LINES(gauge, gauge._max_value)
        else:
            ceil_lines = GAUGE_LINES(gauge, gauge._max_gauge)
        if gauge._min_gauge is None:
            floor_lines = VALUE_LINES(gauge, gauge._min_value)
        else:
            floor_lines = GAUGE_LINES(gauge, gauge._min_gauge)
        cdef:
            Boundary boundary
            Boundary bound
            Boundary b
            ceil = Boundary(ceil_lines, operator.lt)
            floor = Boundary(floor_lines, operator.gt)
            list boundaries = [ceil, floor]
            bint bounded = False
            bint overlapped = False
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
        cdef:
            double time
            double bound_until
            int method
            Momentum momentum
            bint again
            list walked_boundaries
            Line line
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
                    for b in boundaries:
                        if b.line.until < until:
                            break
                    else:
                        break
                    # choose the next boundary.
                    boundary = boundaries[0]
                    for b in boundaries:
                        if b.line.until < boundary.line.until:
                            boundary = b
                    boundary._walk()
                    walked_boundaries = [boundary]
                # calculate velocity.
                if not bounded:
                    velocity = sum(velocities)
                elif overlapped:
                    velocity = bound.best(sum(velocities),
                                          bound.line.velocity())
                else:
                    velocity = sum(v for v in velocities if bound.cmp(v, 0))
                # is still bound?
                if overlapped and bound.cmp(velocity, bound.line.velocity()):
                    bounded, overlapped = False, False
                    again = True
                    continue
                # current value line.
                line = Line(RAY, since, until, value, velocity)
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
                    intersection = line.intersect(boundary.line)
                    ok = intersection[0]
                    if not ok:
                        continue
                    intersection = intersection[1:3]
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


cdef class Line:
    """An abstract class to represent lines between 2 times which start from
    `value`.  Subclasses should describe where lines end.

    .. note::

       Each subclass must implement :meth:`_get`, :meth:`_earlier`,
       :meth:`_later`, and :attr:`velocity` property.

    """

    cdef:
        public int type
        public double since
        public double until
        public double value
        public double extra

    def __cinit__(self, int type,
                  double since, double until, double value,
                  double extra=0):
        assert type in (HORIZON, RAY, SEGMENT)
        self.type = type
        self.since = since
        self.until = until
        self.value = value
        self.extra = extra

    cdef (bint, double, double) intersect(self, Line line):
        """Gets the intersection with the given line.

        :returns: (ok, time, value)

        """
        cdef:
            double time
            double value
            double since
            double until
            double velocity_delta
            double intercept_delta
            Line left
            Line right
        # right is more reliable.
        if self.type < line.type:
            left, right = line, self
        else:
            left, right = self, line
        if math.isinf(right.velocity()):
            # right is almost vertical.
            time = (right.since + right.until) / 2
        else:
            velocity_delta = left.velocity() - right.velocity()
            if velocity_delta == 0:
                # parallel line given.
                return (False, 0, 0)
            intercept_delta = right.intercept() - left.intercept()
            time = intercept_delta / velocity_delta
        since = max(left.since, right.since)
        until = min(left.until, right.until)
        if not since <= time <= until:
            # intersection not in the time range.
            return (False, 0, 0)
        value = left.get(time)
        return (True, time, value)

    cdef double intercept(self):
        """Gets the value-intercept. (Y-intercept)"""
        return self.value - self.velocity() * self.since

    cdef double get(self, double at):
        """Returns the value at the given time.

        :raises ValueError: the given time is out of the time range.
        """
        if not self.since <= at <= self.until:
            raise ValueError('Out of the time range: {0:.2f}~{1:.2f}'
                             ''.format(self.since, self.until))
        if self.type == HORIZON:
            return self._get_horizon(at)
        elif self.type == RAY:
            return self._get_ray(at)
        elif self.type == SEGMENT:
            return self._get_segment(at)
        assert 0

    cdef double guess(self, double at):
        """Returns the value at the given time even the time it out of the time
        range.
        """
        if at < self.since:
            if self.type == HORIZON:
                return self._earlier_horizon(at)
            elif self.type == RAY:
                return self._earlier_ray(at)
            elif self.type == SEGMENT:
                return self._earlier_segment(at)
        elif at > self.until:
            if self.type == HORIZON:
                return self._later_horizon(at)
            elif self.type == RAY:
                return self._later_ray(at)
            elif self.type == SEGMENT:
                return self._later_segment(at)
        else:
            return self.get(at)
        assert 0

    cdef double velocity(self):
        if self.type == HORIZON:
            return self._velocity_horizon()
        elif self.type == RAY:
            return self._velocity_ray()
        elif self.type == SEGMENT:
            return self._velocity_segment()
        assert 0

    # HORIZON

    cdef inline double _get_horizon(self, double at):
        return self.value

    cdef inline double _earlier_horizon(self, double at):
        return self.value

    cdef inline double _later_horizon(self, double at):
        return self.value

    cdef inline double _velocity_horizon(self):
        return 0

    # RAY

    cdef inline double _get_ray(self, double at):
        cdef double velocity = self.extra
        return self.value + velocity * (at - self.since)

    cdef inline double _earlier_ray(self, double at):
        return self.value

    cdef inline double _later_ray(self, double at):
        return self._get(self.until)

    cdef inline double _velocity_ray(self):
        return self.extra

    # SEGMENT

    cdef inline double _get_segment(self, double at):
        cdef double final = self.extra
        return SEGMENT_VALUE(at, self.since, self.until, self.value, final)

    cdef inline double _earlier_segment(self, double at):
        return self.value

    cdef inline double _later_segment(self, double at):
        cdef double final = self.extra
        return final

    cdef inline double _velocity_segment(self):
        cdef double final = self.extra
        return SEGMENT_VELOCITY(self.since, self.until, self.value, final)

    # __repr__

    def __repr__(self):
        cdef str string
        if self.type == HORIZON:
            string = '[HORIZON] {0:.2f}'.format(self.value)
        elif self.type == RAY:  # extra is velocity.
            string = '[RAY] {0:.2f}{1:+.2f}/s'.format(self.value, self.extra)
        elif self.type == SEGMENT:  # extra is final.
            string = '[SEGMENT] {0:.2f}~{1:.2f}'.format(self.value, self.extra)
        else:
            assert 0
        return ('<{0}{1} for {2!r}~{3!r}>'
                ''.format(type(self).__name__, string, self.since, self.until))


cdef class Boundary:

    cdef:
        public Line line
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
