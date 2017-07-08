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


__all__ = ['Determination', 'Line', 'Horizon', 'Ray', 'Segment', 'Boundary']


class Determination(list):
    """Determination of a gauge is a list of `(time, value)` pairs.

    :param determining: a :meth:`Gauge.determine` iterator.
    """

    #: The time when the gauge starts to be in_range of the limits.
    in_range_since = None

    @staticmethod
    def value_lines(gauge, double value):
        yield Horizon(gauge.base[TIME], +inf, value)

    @staticmethod
    def gauge_lines(gauge, other_gauge):
        determination = other_gauge.determination
        first, last = determination[0], determination[-1]
        if gauge.base[TIME] < first[TIME]:
            yield Horizon(gauge.base[TIME], first[TIME], first[VALUE])
        zipped_determination = zip(determination[:-1], determination[1:])
        for (time1, value1), (time2, value2) in zipped_determination:
            yield Segment(time1, time2, value1, value2)
        yield Horizon(last[TIME], +inf, last[VALUE])

    def determine(self, double time, double value, bint in_range=True):
        if self and self[-1][TIME] == time:
            return
        if in_range and self.in_range_since is None:
            self.in_range_since = time
        self.append((time, value))

    def __init__(self, gauge):
        """Determines the transformations from the time when the value set to
        the farthest future.
        """
        cdef double since
        cdef double until
        cdef double value
        cdef double velocity = 0
        cdef list velocities = []
        cdef bint bounded = False
        cdef bint overlapped = False
        since, value = gauge.base
        # boundaries.
        ceil_lines_iter = (self.value_lines(gauge, gauge.max_value)
                           if gauge.max_gauge is None else
                           self.gauge_lines(gauge, gauge.max_gauge))
        floor_lines_iter = (self.value_lines(gauge, gauge.min_value)
                            if gauge.min_gauge is None else
                            self.gauge_lines(gauge, gauge.min_gauge))
        cdef Boundary bound
        cdef Boundary boundary
        cdef ceil = Boundary(ceil_lines_iter, operator.lt)
        cdef floor = Boundary(floor_lines_iter, operator.gt)
        cdef boundaries = [ceil, floor]
        for boundary in boundaries:
            # skip past boundaries.
            while boundary._line.until <= since:
                boundary.walk()
            # check overflowing.
            if bounded:
                continue
            boundary_value = boundary._line.guess(since)
            if boundary._cmp(boundary_value, value):
                bound, bounded, overlapped = boundary, True, False
        cdef double time
        cdef int method
        cdef bint again
        cdef list walked_boundaries
        cdef Boundary b
        for time, method, momentum in gauge.momentum_events():
            # normalize time.
            until = max(time, gauge.base[TIME])
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
                        if b._line.until < until:
                            break
                    else:
                        break
                    # ---
                    # choose the next boundary.
                    # boundary = min(boundaries, key=lambda b: b.line.until)
                    boundary = boundaries[0]
                    for b in boundaries:
                        if b._line.until < boundary._line.until:
                            boundary = b
                    # ---
                    boundary.walk()
                    walked_boundaries = [boundary]
                # calculate velocity.
                if not bounded:
                    velocity = sum(velocities)
                elif overlapped:
                    velocity = bound._best(sum(velocities), bound._line.velocity)
                else:
                    velocity = sum(v for v in velocities if bound._cmp(v, 0))
                # is still bound?
                if overlapped and bound._cmp(velocity, bound._line.velocity):
                    bounded, overlapped = False, False
                    again = True
                    continue
                # current value line.
                line = Ray(since, until, value, velocity)
                if overlapped:
                    bound_until = min(bound._line.until, until)
                    if bound_until == +inf:
                        break
                    # released from the boundary.
                    since, value = (bound_until, bound._line.get(bound_until))
                    self.determine(since, value)
                    continue
                for boundary in walked_boundaries:
                    # find the intersection with a boundary.
                    try:
                        intersection = line.intersect(boundary._line)
                    except ValueError:
                        continue
                    if intersection[TIME] == since:
                        continue
                    again = True  # iterate with same boundaries again.
                    bound, bounded, overlapped = boundary, True, True
                    since, value = intersection
                    # clamp by the boundary.
                    value = boundary._best(value, boundary._line.guess(since))
                    self.determine(since, value)
                    break
                if bounded:
                    continue  # the intersection was found.
                for boundary in walked_boundaries:
                    # find missing intersection caused by floating-point
                    # inaccuracy.
                    bound_until = min(boundary._line.until, until)
                    if bound_until == +inf or bound_until < since:
                        continue
                    boundary_value = boundary._line.get(bound_until)
                    if boundary.cmp_eq(line.get(bound_until), boundary_value):
                        continue
                    bound, bounded, overlapped = boundary, True, True
                    since, value = bound_until, boundary_value
                    self.determine(since, value)
                    break
            if until == +inf:
                break
            # determine the final node in the current itreration.
            value += velocity * (until - since)
            self.determine(until, value, in_range=not bounded or overlapped)
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

    cdef _line
    cdef _lines_iter
    cdef _cmp
    cdef _best

    def __init__(self, lines_iter, cmp=operator.lt):
        assert cmp in [operator.lt, operator.gt]
        self._lines_iter = lines_iter
        self._cmp = cmp
        self._best = {operator.lt: min, operator.gt: max}[cmp]
        self.walk()

    @property
    def line(self):
        return self._line

    @property
    def cmp(self):
        return self._cmp

    @property
    def best(self):
        return self._best

    def walk(self):
        """Choose the next line."""
        self._line = next(self._lines_iter)

    def cmp_eq(self, double x, double y):
        return x == y or self._cmp(x, y)

    def cmp_inv(self, double x, double y):
        return x != y and not self._cmp(x, y)

    def __repr__(self):
        return ('<{0} line={1}, cmp={2}>'
                ''.format(type(self).__name__, self._line, self._cmp))
