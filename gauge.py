# -*- coding: utf-8 -*-
"""
    gauge
    ~~~~~

    Deterministic linear gauge library.

    :copyright: (c) 2013-2014 by Heungsub Lee
    :license: BSD, see LICENSE for more details.
"""
from collections import namedtuple
import math
import operator
from time import time as now
import warnings

from sortedcontainers import SortedList, SortedListWithKey


__all__ = ['Gauge', 'Momentum']
__version__ = '0.1.0'


ADD = 1
REMOVE = 0
ceil = 'ceil'
floor = 'floor'
AT = 0
VALUE = 1


inf = float('inf')


def deprecate(message, *args, **kwargs):
    warnings.warn(DeprecationWarning(message.format(*args, **kwargs)))


def now_or(at):
    return now() if at is None else float(at)


def or_inf(at):
    return inf if at is None else at


def clamp(x, min_, max_):
    return max(min(x, max_), min_)


class Gauge(object):
    """Represents a gauge.  A gauge has a value at any moment.  It can be
    modified by an user's adjustment or an effective momentum.
    """

    #: The value set by an user.
    value = 0

    #: The time when the value was set.
    set_at = None

    #: A sorted list of momenta.  The items are :class:`Momentum` objects.
    momenta = None

    def __init__(self, value, max, min=0, at=None):
        self._max = max
        self._min = min
        self.value = value
        self.set_at = now_or(at)
        self.momenta = SortedListWithKey(key=lambda m: m[2])  # sort by until
        self._plan = SortedList()

    @property
    def determination(self):
        """Returns the cached determination.  If there's no the cache, it
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
        """Clears the cached determination.  If you touches the determination
        at the next first time, that will be redetermined.
        """
        try:
            del self._determination
        except AttributeError:
            pass

    @property
    def max(self):
        return self._max

    @max.setter
    def max(self, max):
        self.set_max(max)

    @property
    def min(self):
        return self._min

    @min.setter
    def min(self, min):
        self.set_min(min)

    def _set_limits(self, min=None, max=None,
                    clamp=False, limit=None, at=None):
        if limit is not None:
            clamp = limit
            # deprecated since v0.0.12
            deprecate('Use clamp={0} instead of limit={0}', limit)
        if clamp:
            at = now_or(at)
            value = self.get(at=at)
        if min is not None:
            self._min = min
        if max is not None:
            self._max = max
        if clamp:
            if max is not None and value > max:
                limited = max
            elif min is not None and value < min:
                limited = min
            else:
                limited = None
            if limited is not None:
                self.forget_past(limited, at=at)
                return
        del self.determination

    def set_max(self, max, clamp=False, limit=None, at=None):
        """Changes the maximum.

        :param max: the value to set as the maximum.
        :param clamp: limits the current value to be below the new maximum.
                      (default: ``True``)
        :param at: the time to change.  (default: now)
        """
        self._set_limits(max=max, clamp=clamp, limit=limit, at=at)

    def set_min(self, min, clamp=False, limit=None, at=None):
        """Changes the minimum.

        :param min: the value to set as the minimum.
        :param clamp: limits the current value to be above the new minimum.
                      (default: ``True``)
        :param at: the time to change.  (default: now)
        """
        self._set_limits(min=min, clamp=clamp, limit=limit, at=at)

    def _current_value_and_velocity(self, at=None):
        at = now_or(at)
        determination = self.determination
        if len(determination) == 1:
            # skip bisect_left() because it is expensive
            x = 0
        else:
            x = determination.bisect_left((at,))
        if x == 0:
            return (determination[0][VALUE], 0.)
        try:
            next_time, next_value = determination[x]
        except IndexError:
            return (determination[-1][VALUE], 0.)
        prev_time, prev_value = determination[x - 1]
        t = float(at - prev_time) / (next_time - prev_time)
        delta = next_value - prev_value
        value = prev_value + t * delta
        velocity = delta / (next_time - prev_time)
        return (value, velocity)

    def get(self, at=None):
        """Predicts the current value.

        :param at: the time to observe.  (default: now)
        """
        value, velocity = self._current_value_and_velocity(at)
        return value

    def velocity(self, at=None):
        """Predicts the current velocity.

        :param at: the time to observe.  (default: now)
        """
        value, velocity = self._current_value_and_velocity(at)
        return velocity

    def incr(self, delta, over=False, clamp=False, limit=None, at=None):
        """Increases the value by the given delta immediately.  The
        determination would be changed.

        :param delta: the value to increase.
        :param limit: checks if the value is in the range.  (default: ``True``)
        :param at: the time to increase.  (default: now)

        :raises ValueError: the value is out of the range.
        """
        if limit is not None:
            over = not limit
            # deprecated since v0.0.12
            deprecate('Use over={0} instead of limit={1}', over, limit)
        at = now_or(at)
        prev_value = self.get(at=at)
        value = prev_value + delta
        if over:
            pass
        elif clamp:
            if delta > 0 and value > self.max:
                value = max(prev_value, self.max)
            elif delta < 0 and value < self.min:
                value = min(prev_value, self.min)
        else:
            if delta > 0 and value > self.max:
                raise ValueError('The value to set is bigger than the '
                                 'maximum ({0} > {1})'.format(value, self.max))
            elif delta < 0 and value < self.min:
                raise ValueError('The value to set is smaller than the '
                                 'minimum ({0} < {1})'.format(value, self.min))
        self.forget_past(value, at=at)
        return value

    def decr(self, delta, over=False, clamp=False, limit=None, at=None):
        """Decreases the value by the given delta immediately.  The
        determination would be changed.

        :param delta: the value to decrease.
        :param limit: checks if the value is in the range.  (default: ``True``)
        :param at: the time to decrease.  (default: now)

        :raises ValueError: the value is out of the range.
        """
        return self.incr(-delta, over=over, clamp=clamp, limit=limit, at=at)

    def set(self, value, over=False, clamp=False, limit=None, at=None):
        """Sets the current value immediately.  The determination would be
        changed.

        :param value: the value to set.
        :param limit: checks if the value is in the range.  (default: ``True``)
        :param at: the time to set.  (default: now)

        :raises ValueError: the value is out of the range.
        """
        at = now_or(at)
        delta = value - self.get(at=at)
        return self.incr(delta, over=over, clamp=clamp, limit=limit, at=at)

    def when(self, value, after=0):
        """When the gauge reaches to the goal value.

        :param value: the goal value.
        :param after: take (n+1)th time.  (default: 0)

        :raises ValueError: the gauge will not reach to the goal value.
        """
        x = 0
        for x, at in enumerate(self.whenever(value)):
            if x == after:
                return at
        form = 'The gauge will not reach to {0}' + \
               (' more than {1} times' if x else '')
        raise ValueError(form.format(value, x))

    def whenever(self, value):
        """Yields multiple times when the gauge reaches to the goal value.

        :param value: the goal value.
        """
        if self.determination:
            determination = self.determination
            first_time, first_value = determination[0]
            if first_value == value:
                yield first_time
            for prev, next in zip(determination[:-1], determination[1:]):
                prev_time, prev_value = prev
                next_time, next_value = next
                if prev_value < value <= next_value:
                    pass
                elif prev_value > value >= next_value:
                    pass
                else:
                    continue
                t = (value - prev_value) / float(next_value - prev_value)
                yield prev_time + (next_time - prev_time) * t

    def _make_momentum(self, velocity_or_momentum, since=None, until=None):
        """Makes a :class:`Momentum` object by the given arguments.

        Override this if you want to use your own momentum class.

        :param velocity_or_momentum: a :class:`Momentum` object or just a
                                     number for the velocity.
        :param since: if the first argument is a velocity, it is the time to
                      start to affect the momentum.  (default: ``None``)
        :param until: if the first argument is a velocity, it is the time to
                      finish to affect the momentum.  (default: ``None``)

        :raises ValueError: `since` later than or same with `until`.
        :raises TypeError: the first argument is a momentum, but other
                           arguments passed.
        """
        if isinstance(velocity_or_momentum, Momentum):
            if not (since is until is None):
                raise TypeError('Arguments behine the first argument as a '
                                'momentum should be None')
            momentum = velocity_or_momentum
        else:
            velocity = velocity_or_momentum
            momentum = Momentum(velocity, since, until)
        since, until = momentum.since, momentum.until
        if since is None or until is None or since < until:
            pass
        else:
            raise ValueError('\'since\' should be earlier than \'until\'')
        return momentum

    def add_momentum(self, *args, **kwargs):
        """Adds a momentum.  A momentum includes the velocity and the times to
        start to affect and to stop to affect.  The determination would be
        changed.

        All arguments will be passed to :meth:`_make_momentum`.

        :returns: a momentum object.  Use this to remove the momentum by
                  :meth:`remove_momentum`.

        :raises ValueError: `since` later than or same with `until`.
        """
        momentum = self._make_momentum(*args, **kwargs)
        since, until = momentum.since, momentum.until
        self.momenta.add(momentum)
        self._plan.add((since, ADD, momentum))
        if until is not None:
            self._plan.add((until, REMOVE, momentum))
        del self.determination
        return momentum

    def remove_momentum(self, *args, **kwargs):
        """Removes the given momentum.  The determination would be changed.

        All arguments will be passed to :meth:`_make_momentum`.

        :raises ValueError: the given momentum not in the gauge.
        """
        momentum = self._make_momentum(*args, **kwargs)
        try:
            self.momenta.remove(momentum)
        except ValueError:
            raise ValueError('{0} not in the gauge'.format(momentum))
        del self.determination

    def _coerce_and_remove_momenta(self, value=None, at=None,
                                   start=None, stop=None):
        """Coerces to set the value and removes the momenta between indexes of
        ``start`` and ``stop``.

        :param value: the value to set coercively.  (default: the current
                      value)
        :param at: the time to set.  (default: now)
        :param start: the starting index of momentum removal.
                      (default: the first)
        :param stop: the stopping index of momentum removal.
                     (default: the last)
        """
        at = now_or(at)
        if value is None:
            value = self.get(at=at)
        self.value = value
        self.set_at = at
        del self.momenta[start:stop]
        del self.determination
        return value

    def clear_momenta(self, value=None, at=None):
        """Removes all momenta.  The value is set as the current value.  The
        determination would be changed.

        :param value: the value to set coercively.
        :param at: the time base.  (default: now)
        """
        return self._coerce_and_remove_momenta(value, at)

    def forget_past(self, value=None, at=None):
        """Discards the momenta which doesn't effect anymore.

        :param value: the value to set coercively.
        :param at: the time base.  (default: now)
        """
        at = now_or(at)
        start = self.momenta.bisect_right((inf, inf, None))
        stop = self.momenta.bisect_left((-inf, -inf, at))
        return self._coerce_and_remove_momenta(value, at, start, stop)

    def walk_segs(self, number_or_gauge):
        if isinstance(number_or_gauge, Gauge):
            determination = number_or_gauge.determine()
            # t, v = determination[0]
            # yield Segment(value=v, velocity=0, since=None, until=t)
            for (t1, v1), (t2, v2) in zip(determination[:-1],
                                          determination[1:]):
                velocity = (v2 - v1) / (t2 - t1)
                yield Segment(value=v1, velocity=velocity, since=t1, until=t2)
            t, v = determination[-1]
            yield Segment(value=v, velocity=0, since=t, until=None)
        else:
            value = number_or_gauge
            yield Segment(value=value, velocity=0,
                          since=self.set_at, until=None)

    def determine2(self, debug=False):
        determination = SortedList()
        ceil = Boundary(self.walk_segs(self.max), operator.lt)
        floor = Boundary(self.walk_segs(self.min), operator.gt)
        # which boundary the current segment bound to
        bound = None
        overlapped = False
        prev_time = self.set_at
        value = self.value
        velocities = []
        velocity = 0
        # from click import echo, secho, style
        # def repr_seg(seg):
        #     return '{0:.2f}{1:+.2f}/s in {2}~{3}'.format(*seg)
        def deter(time, value, ctx=None):
            if determination and determination[-1][AT] == time:
                pass
            else:
                determination.add((time, value))
                # if debug and ctx is not None:
                #     secho(' => {0:.2f}: {1:.2f} ({2})'
                #           ''.format(time, value, ctx), fg='green')
            return time, value
        def calc_value(time):
            return value + velocity * (time - prev_time)
        def calc_velocity():
            if bound is None:
                return sum(velocities)
            if overlapped:
                return bound.best(sum(velocities), bound.seg.velocity)
            else:
                return sum(v for v in velocities if bound.cmp(v, 0))
        def out_of_bound(seg, boundary):
            boundary_value = boundary.seg.guess(seg.since)
            return boundary.cmp_inv(seg.value, boundary_value)
        def deter_intersection(seg, boundary):
            intersection = seg.intersect(boundary.seg)
            if intersection[AT] == seg.since:
                raise ValueError
            deter(*intersection)  # inter
            return intersection[AT], intersection[VALUE], boundary, True
        # if debug:
        #     print
        deter(prev_time, value, 'init')
        for time, method, momentum in self._plan:
            if momentum not in self.momenta:
                continue
            # normalize time
            time = max(time, self.set_at)
            seg = Segment(value, velocity, prev_time, time)
            # if debug:
            #     echo('{0} {1:+.2f} {2} {3}'.format(
            #          style(' {0} '.format(time), 'cyan', reverse=True),
            #          velocity,
            #          style({ceil: 'ceil', floor: 'floor', None: ''}[bound],
            #                'cyan'),
            #          style('overlapped' if overlapped else '', 'cyan')))
            # skip past boundaries
            for boundary in [ceil, floor]:
                while or_inf(boundary.seg.until) <= prev_time:
                    boundary.walk()
            for boundary in [ceil, floor]:
                if out_of_bound(seg, boundary):
                    bound, overlapped = boundary, False
                    break
            first = True
            while prev_time < time:
                if first:
                    # first iteration doesn't require to choose boundaries
                    first = False
                else:
                    # choose next boundaries
                    ceil_until = or_inf(ceil.seg.until)
                    floor_until = or_inf(floor.seg.until)
                    if ceil_until >= time and floor_until >= time:
                        break
                    if ceil_until < time:
                        ceil.walk()
                    if floor_until < time:
                        floor.walk()
                # current segment
                velocity = calc_velocity()
                seg = Segment(value, velocity, prev_time, time)
                # still bound?
                if bound is not None and overlapped:
                    if bound.cmp(velocity, bound.seg.velocity):
                        bound, overlapped = None, False
                # if debug:
                #     echo('    {0} between {1} and {2} {3} {4}'.format(
                #          style(repr_seg(seg), 'red'),
                #          style(repr_seg(ceil.seg), 'red'),
                #          style(repr_seg(floor.seg), 'red'),
                #          style({ceil: 'ceil', floor: 'floor', None: ''}
                #                [bound], 'cyan'),
                #          style('overlapped' if overlapped else '',
                #                'cyan' if overlapped else '')))
                if bound is None:
                    for boundary in [ceil, floor]:
                        # check if out of bound
                        if out_of_bound(seg, boundary):
                            bound, overlapped = boundary, False
                            break
                        # check if there's the intersection between the current
                        # segment and boundary
                        try:
                            prev_time, value, bound, overlapped = \
                                deter_intersection(seg, boundary)
                        except ValueError:
                            pass
                        else:
                            break
                elif overlapped:
                    # release from bound
                    bound_until = or_inf(bound.seg.until)
                    if prev_time < bound_until:
                        bound_until = min(bound_until, time)
                        prev_time, value = \
                            deter(bound_until, seg.get(bound_until))  # release
                else:
                    # returned to safe zone
                    try:
                        prev_time, value, bound, overlapped = \
                            deter_intersection(seg, bound)
                    except ValueError:
                        pass
            velocity = calc_velocity()
            value = calc_value(time)
            deter(time, value, 'normal')
            # prepare the next iteration
            if method == ADD:
                velocities.append(momentum.velocity)
            elif method == REMOVE:
                velocities.remove(momentum.velocity)
            prev_time = time
        # finalize
        final_time = min(or_inf(ceil.seg.until), or_inf(floor.seg.until))
        if math.isinf(final_time):
            for boundary in [ceil, floor]:
                velocity = calc_velocity()
                if not velocity:
                    break
                seg = Segment(value, velocity, prev_time, None)
                try:
                    prev_time, value, bound, overlapped = \
                        deter_intersection(seg, boundary)
                except ValueError:
                    pass
        else:
            value = calc_value(final_time)
            deter(final_time, value, 'final')
        return determination

    def determine(self):
        """Determines the transformations from the time when the value set to
        the farthest future.

        :returns: a sorted list of the determination.
        """
        return self.determine2()
        determination = SortedList()
        # accumulated velocities and the sum of velocities
        velocities = []
        total_velocity = 0
        # variables not set
        method = None
        span = None
        # default
        time = self.set_at
        value = self.value
        momentum = None
        prev_time = None
        # functions
        deter = lambda time, value: determination.add((time, value))
        time_to_reach = lambda goal: (goal - value) / total_velocity
        # trivial variables
        x = 0
        momentum = None
        prev_time = None
        while True:
            if span is None:
                # skip the first loop
                pass
            else:
                # calculate the change
                if value > self.max:
                    limited = self.max
                    total_velocity = sum(v for v in velocities if v < 0)
                elif value < self.min:
                    limited = self.min
                    total_velocity = sum(v for v in velocities if v > 0)
                else:
                    limited = None
                    total_velocity = sum(velocities)
                if limited is not None and total_velocity != 0:
                    # the previous value is out of the range
                    d = time_to_reach(limited)
                    if 0 < d < span:
                        span -= d
                        prev_time += d
                        value = limited
                        deter(prev_time, value)
                        total_velocity = sum(velocities)
                new_value = value + total_velocity * span
                if new_value > self.max and total_velocity > 0:
                    limited = self.max
                elif new_value < self.min and total_velocity < 0:
                    limited = self.min
                else:
                    limited = None
                if limited is None:
                    value = new_value
                else:
                    # the new value is out of the range
                    d = time_to_reach(limited)
                    if 0 < d:
                        value = limited
                        deter(prev_time + d, value)
            if span == inf:
                # the final loop
                break
            elif span is None or span:
                # determine the current point
                deter(time, value)
            # apply the current plan
            if method == ADD:
                velocities.append(momentum.velocity)
            elif method == REMOVE:
                velocities.remove(momentum.velocity)
            # prepare the next iteration
            prev_time = time
            try:
                while True:
                    time, method, momentum = self._plan[x]
                    if momentum in self.momenta:
                        break
                    del self._plan[x]
            except IndexError:
                span = inf
                continue
            # normalize time
            if time is None:
                time = self.set_at
            else:
                time = float(max(self.set_at, time))
            span = time - prev_time
            x += 1
        return determination

    def __getstate__(self):
        return (self.value, self.set_at, self._max, self._min,
                map(tuple, self.momenta))

    def __setstate__(self, state):
        value, set_at, max, min, momenta = state
        self.__init__(value, max=max, min=min, at=set_at)
        for momentum in momenta:
            self.add_momentum(*momentum)

    def __repr__(self, at=None):
        at = now_or(at)
        value = self.get(at=at)
        form = '<{0} {1:.2f}'
        form += '/{2}>' if self.min == 0 else ' between {3}~{2}>'
        return form.format(type(self).__name__, value, self.max, self.min)

    # deprecated features

    def current(self, at=None):
        # deprecated since v0.0.5
        deprecate('Use Gauge.get() instead')
        return self.get(at=at)

    current.__doc__ = get.__doc__


class Momentum(namedtuple('Momentum', ['velocity', 'since', 'until'])):
    """A power of which increases or decreases the gauge continually between a
    specific period.
    """

    # XXX: is better since=-inf, until=inf ?
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


class Segment(namedtuple('Segment', ['value', 'velocity', 'since', 'until'])):
    # `since` cannot be None, but `until` can.

    def get(self, at):
        if not self.since <= at <= or_inf(self.until):
            raise ValueError('Out of range')
        return self.value + self.velocity * (at - self.since)

    def guess(self, at):
        if at < self.since:
            return self.value
        elif self.until is not None and self.until < at:
            return self.final()
        else:
            return self.get(at)

    def final(self):
        return self.get(self.until)

    def intersect(self, seg):
        # y-intercepts
        y_intercept = (self.value - self.velocity * self.since)
        seg_y_intercept = (seg.value - seg.velocity * seg.since)
        try:
            at = (seg_y_intercept - y_intercept) / \
                 (self.velocity - seg.velocity)
        except ZeroDivisionError:
            raise ValueError('Parallel segment')
        since = max(self.since, seg.since)
        until = min(or_inf(self.until), or_inf(seg.until))
        if since <= at <= until:
            pass
        else:
            raise ValueError('Intersection not in the range')
        value = self.get(at)
        return (at, value)


class Boundary(object):

    #: The current segment.  To select next segment, call :meth:`walk`.
    seg = None

    #: The segment iterator.
    segs_iter = None

    #: Compares two values.  Choose one of `operator.lt` and `operator.gt`.
    cmp = None

    #: Returns the best value in an iterable or arguments.  Usually it is
    #: indicated from :attr:`cmp` function.  `operator.lt` indicates
    #: :func:`min` and `operator.gt` indicates :func:`max`.
    best = None

    def __init__(self, segs_iter, cmp=operator.lt, best=None):
        assert cmp in [operator.lt, operator.gt]
        self.segs_iter = segs_iter
        self.cmp = cmp
        if best is None:
            best = {operator.lt: min, operator.gt: max}[cmp]
        self.best = best
        self.walk()

    def walk(self):
        self.seg = next(self.segs_iter)

    def cmp_eq(self, x, y):
        return x == y or self.cmp(x, y)

    def cmp_inv(self, x, y):
        return not self.cmp_eq(x, y)

    def best_inv(self, *args, **kwargs):
        return {min: max, max: min}[self.best](*args, **kwargs)
