# -*- coding: utf-8 -*-
"""
    gauge
    ~~~~~

    Deterministic linear gauge library.

    :copyright: (c) 2013-2014 by Heungsub Lee
    :license: BSD, see LICENSE for more details.

"""
from collections import namedtuple
import operator
from time import time as now
import warnings
import weakref

from sortedcontainers import SortedList, SortedListWithKey


__all__ = ['Gauge', 'Momentum']
__version__ = '0.1.1'


# indices
TIME = 0
VALUE = 1

# events
ADD = +1
REMOVE = -1


inf = float('inf')


def deprecate(message, *args, **kwargs):
    warnings.warn(DeprecationWarning(message.format(*args, **kwargs)))


def now_or(time):
    return now() if time is None else float(time)


class Gauge(object):
    """Represents a gauge.  A gauge has a value at any moment.  It can be
    modified by an user's adjustment or an effective momentum.
    """

    #: The base time and value.
    base = (None, 0)

    #: A sorted list of momenta.  The items are :class:`Momentum` objects.
    momenta = None

    def __init__(self, value, max, min=0, at=None):
        at = now_or(at)
        self.base = (at, value)
        self.momenta = SortedListWithKey(key=lambda m: m[2])  # sort by until
        self.set_max(max, at=at)
        self.set_min(min, at=at)
        self._events = SortedList()
        self._links = set()

    @property
    def determination(self):
        """The cached determination.  If there's no the cache, it redetermines
        and caches that.

        A determination is a sorted list of 2-dimensional points which take
        times as x-values, gauge values as y-values.
        """
        try:
            return self._determination
        except AttributeError:
            pass
        # redetermine and cache.
        self._determination = SortedList()
        prev_time = None
        for time, value in self.determine():
            if prev_time == time:
                continue
            self._determination.add((time, value))
            prev_time = time
        return self._determination

    def invalidate(self):
        """Invalidates the cached determination.  If you touches the
        determination at the next first time, that will be redetermined.

        You don't need to call this method because all mutating methods such as
        :meth:`incr` or :meth:`add_momentum` calls it.
        """
        # invalidate linked gauges together.  A linked gauge refers this gauge
        # as a limit.
        try:
            links = list(self._links)
        except AttributeError:
            pass
        else:
            for gauge_ref in links:
                gauge = gauge_ref()
                if gauge is None:
                    # the gauge has gone away
                    self._links.remove(gauge_ref)
                    continue
                gauge.invalidate()
        # remove the cached determination.
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

    def _get_limit(self, limit, at=None):
        if isinstance(limit, Gauge):
            return limit.get(at)
        else:
            return limit

    def get_max(self, at=None):
        """Predicts the current maximum value."""
        return self._get_limit(self.max, at=at)

    def get_min(self, at=None):
        """Predicts the current minimum value."""
        return self._get_limit(self.min, at=at)

    def _set_limits(self, max=None, min=None, clamp=False, at=None):
        for limit, attr in [(max, '_max'), (min, '_min')]:
            if limit is None:
                continue
            try:
                prev_limit = getattr(self, attr)
            except AttributeError:
                pass
            else:
                if isinstance(prev_limit, Gauge):
                    # unlink this gauge from the previous limiting gauge.
                    prev_limit._links.discard(weakref.ref(self))
            if isinstance(limit, Gauge):
                # link this gauge to the new limiting gauge.
                limit._links.add(weakref.ref(self))
            # set the internal attribute.
            setattr(self, attr, limit)
        if clamp:
            # clamp the current value.
            at = now_or(at)
            value = self.get(at=at)
            max_ = value if max is None else self.get_max(at=at)
            min_ = value if min is None else self.get_min(at=at)
            if value > max_:
                limited = max_
            elif value < min_:
                limited = min_
            else:
                limited = None
            if limited is not None:
                self.forget_past(limited, at=at)
                # :meth:`forget_past` calls :meth:`invalidate`.
                return
        self.invalidate()

    def set_max(self, max, clamp=False, at=None):
        """Changes the maximum.

        :param max: a number or gauge to set as the maximum.
        :param clamp: limits the current value to be below the new maximum.
                      (default: ``True``)
        :param at: the time to change.  (default: now)
        """
        self._set_limits(max=max, clamp=clamp, at=at)

    def set_min(self, min, clamp=False, at=None):
        """Changes the minimum.

        :param min: a number or gauge to set as the minimum.
        :param clamp: limits the current value to be above the new minimum.
                      (default: ``True``)
        :param at: the time to change.  (default: now)
        """
        self._set_limits(min=min, clamp=clamp, at=at)

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
        time = float(at - prev_time) / (next_time - prev_time)
        delta = next_value - prev_value
        value = prev_value + time * delta
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

    def incr(self, delta, over=False, clamp=False, at=None):
        """Increases the value by the given delta immediately.  The
        determination would be changed.

        :param delta: the value to increase.
        :param limit: checks if the value is in the range.  (default: ``True``)
        :param at: the time to increase.  (default: now)

        :raises ValueError: the value is out of the range.
        """
        at = now_or(at)
        prev_value = self.get(at=at)
        value = prev_value + delta
        max_, min_ = self.get_max(at), self.get_min(at)
        if over:
            pass
        elif clamp:
            if delta > 0 and value > max_:
                value = max(prev_value, max_)
            elif delta < 0 and value < min_:
                value = min(prev_value, min_)
        else:
            if delta > 0 and value > max_:
                raise ValueError('The value to set is bigger than the '
                                 'maximum ({0} > {1})'.format(value, max_))
            elif delta < 0 and value < min_:
                raise ValueError('The value to set is smaller than the '
                                 'minimum ({0} < {1})'.format(value, min_))
        self.forget_past(value, at=at)
        return value

    def decr(self, delta, over=False, clamp=False, at=None):
        """Decreases the value by the given delta immediately.  The
        determination would be changed.

        :param delta: the value to decrease.
        :param limit: checks if the value is in the range.  (default: ``True``)
        :param at: the time to decrease.  (default: now)

        :raises ValueError: the value is out of the range.
        """
        return self.incr(-delta, over=over, clamp=clamp, at=at)

    def set(self, value, over=False, clamp=False, at=None):
        """Sets the current value immediately.  The determination would be
        changed.

        :param value: the value to set.
        :param limit: checks if the value is in the range.  (default: ``True``)
        :param at: the time to set.  (default: now)

        :raises ValueError: the value is out of the range.
        """
        at = now_or(at)
        delta = value - self.get(at=at)
        return self.incr(delta, over=over, clamp=clamp, at=at)

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
            zipped_determination = zip(determination[:-1], determination[1:])
            for (time1, value1), (time2, value2) in zipped_determination:
                if not (value1 < value <= value2 or value1 > value >= value2):
                    continue
                ratio = (value - value1) / float(value2 - value1)
                yield (time1 + (time2 - time1) * ratio)

    def _make_momentum(self, velocity_or_momentum, since=None, until=None):
        """Makes a :class:`Momentum` object by the given arguments.

        Override this if you want to use your own momentum class.

        :param velocity_or_momentum: a :class:`Momentum` object or just a
                                     number for the velocity.
        :param since: if the first argument is a velocity, it is the time to
                      start to affect the momentum.  (default: ``-inf``)
        :param until: if the first argument is a velocity, it is the time to
                      finish to affect the momentum.  (default: ``+inf``)

        :raises ValueError: `since` later than or same with `until`.
        :raises TypeError: the first argument is a momentum, but other
                           arguments passed.
        """
        if isinstance(velocity_or_momentum, Momentum):
            if not (since is until is None):
                raise TypeError('Arguments behind the first argument as a '
                                'momentum should be None')
            momentum = velocity_or_momentum
        else:
            velocity = velocity_or_momentum
            if since is None:
                since = -inf
            if until is None:
                until = +inf
            momentum = Momentum(velocity, since, until)
        since, until = momentum.since, momentum.until
        if since == -inf or until == +inf or since < until:
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
        self._events.add((since, ADD, momentum))
        if until != +inf:
            self._events.add((until, REMOVE, momentum))
        self.invalidate()
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
        self.invalidate()

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
        self.base = (at, value)
        del self.momenta[start:stop]
        self.invalidate()
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
        start = self.momenta.bisect_right((+inf, +inf, -inf))
        stop = self.momenta.bisect_left((-inf, -inf, at))
        return self._coerce_and_remove_momenta(value, at, start, stop)

    def walk_events(self):
        """Yields momentum adding and removing events.  An event is a tuple of
        ``(time, ADD|REMOVE, momentum)``.
        """
        yield (self.base[TIME], None, None)
        for time, method, momentum in list(self._events):
            if momentum not in self.momenta:
                self._events.remove((time, method, momentum))
                continue
            yield time, method, momentum
        yield (+inf, None, None)

    def walk_segs(self, number_or_gauge):
        """Yields :class:`Segment`s on the graph from `number_or_gauge`.  If
        `number_or_gauge` is a gauge, the graph is the determination of the
        gauge.  Otherwise, just a horizontal line which has the number as the
        Y-intercept.
        """
        if isinstance(number_or_gauge, Gauge):
            determination = number_or_gauge.determination
            first, last = determination[0], determination[-1]
            yield Segment(first[VALUE], 0, self.base[TIME], first[TIME])
            zipped_determination = zip(determination[:-1], determination[1:])
            for (time1, value1), (time2, value2) in zipped_determination:
                velocity = (value2 - value1) / (time2 - time1)
                yield Segment(value1, velocity, time1, time2)
            yield Segment(last[VALUE], 0, last[TIME], +inf)
        else:
            # just a number.
            value = number_or_gauge
            yield Segment(value, 0, self.base[TIME], +inf)

    def determine(self):
        """Determines the transformations from the time when the value set to
        the farthest future.
        """
        since, value = self.base
        velocity, velocities = 0, []
        bound, overlapped = None, False
        # boundaries.
        ceil = Boundary(self.walk_segs(self.max), operator.lt)
        floor = Boundary(self.walk_segs(self.min), operator.gt)
        boundaries = [ceil, floor]
        # skip past boundaries.
        for boundary in boundaries:
            while boundary.seg.until <= since:
                boundary.walk()
        for time, method, momentum in self.walk_events():
            # normalize time.
            until = max(time, self.base[TIME])
            # check if the value is out of bound.
            for boundary in boundaries:
                boundary_value = boundary.seg.guess(since)
                if boundary.cmp_inv(value, boundary_value):
                    bound, overlapped = boundary, False
                    break
            # if True, An iteration doesn't choose next boundaries.  The first
            # iteration doesn't require to choose next boundaries.
            again = True
            while since < until:
                if again:
                    again = False
                else:
                    # stop the loop if all boundaries have been proceeded.
                    if all(b.seg.until >= until for b in boundaries):
                        break
                    # choose next boundaries.
                    for boundary in boundaries:
                        if boundary.seg.until < until:
                            boundary.walk()
                # calculate velocity.
                if bound is None:
                    velocity = sum(velocities)
                elif overlapped:
                    velocity = bound.best(sum(velocities), bound.seg.velocity)
                else:
                    velocity = sum(v for v in velocities if bound.cmp(v, 0))
                # is still bound?
                if overlapped and bound.cmp(velocity, bound.seg.velocity):
                    bound, overlapped = None, False
                # current segment.
                seg = Segment(value, velocity, since, until)
                if overlapped:
                    bound_until = min(bound.seg.until, until)
                    if bound_until == +inf:
                        break
                    # released from the boundary.
                    since, value = (bound_until, seg.get(bound_until))
                    yield (since, value)
                    continue
                for boundary in boundaries:
                    # find the intersection with a boundary.
                    try:
                        intersection = seg.intersection(boundary.seg)
                    except ValueError:
                        continue
                    if intersection[TIME] == seg.since:
                        continue
                    since, value = intersection
                    bound, overlapped = boundary, True
                    again = True  # iterate with same boundaries again.
                    yield (since, value)
                    break
            if until == +inf:
                break
            # determine the last node in the current itreration.
            value += velocity * (until - since)
            yield (until, value)
            # prepare the next iteration.
            if method == ADD:
                velocities.append(momentum.velocity)
            elif method == REMOVE:
                velocities.remove(momentum.velocity)
            since = until

    def __getstate__(self):
        momenta = list(map(tuple, self.momenta))
        return (self.base, self._max, self._min, momenta)

    def __setstate__(self, state):
        base, max, min, momenta = state
        self.__init__(base[VALUE], max=max, min=min, at=base[TIME])
        for momentum in momenta:
            self.add_momentum(*momentum)

    def __repr__(self, at=None):
        """Example strings:

        - ``<Gauge 0.00/2.00>``
        - ``<Gauge 0.00 between 1.00~2.00>``
        - ``<Gauge 0.00 between <Gauge 0.00/2.00>~<Gauge 2.00/2.00>>``

        """
        at = now_or(at)
        value = self.get(at=at)
        hyper = False
        limit_reprs = []
        for limit in [self.max, self.min]:
            if isinstance(limit, Gauge):
                hyper = True
                limit_reprs.append('{0!r}'.format(limit))
            else:
                limit_reprs.append('{0:.2f}'.format(limit))
        form = '<{0} {1:.2f}'
        if not hyper and self.min == 0:
            form += '/{2}>'
        else:
            form += ' between {3}~{2}>'
        return form.format(type(self).__name__, value, *limit_reprs)

    # deprecated features

    @property
    def set_at(self):
        # deprecated since v0.1.0
        deprecate('Get Gauge.base[0] instead')
        return self.base[TIME]

    @set_at.setter
    def set_at(self, time):
        # deprecated since v0.1.0
        deprecate('Update Gauge.base instead')
        self.base = (time, self.base[VALUE])

    @property
    def value(self):
        # deprecated since v0.1.0
        deprecate('Get Gauge.base[1] instead')
        return self.base[VALUE]

    @value.setter
    def value(self, value):
        # deprecated since v0.1.0
        deprecate('Update Gauge.base instead')
        self.base = (self.base[TIME], value)

    def current(self, at=None):
        # deprecated since v0.0.5
        deprecate('Use Gauge.get() instead')
        return self.get(at=at)

    current.__doc__ = get.__doc__


class Momentum(namedtuple('Momentum', ['velocity', 'since', 'until'])):
    """A power of which increases or decreases the gauge continually between a
    specific period.
    """

    def __new__(cls, velocity, since=-inf, until=+inf):
        velocity = float(velocity)
        return super(Momentum, cls).__new__(cls, velocity, since, until)

    def __repr__(self):
        string = '<{0} {1:+.2f}/s'.format(type(self).__name__, self.velocity)
        if self.since != -inf or self.until != +inf:
            string += ' ' + '~'.join([
                '' if self.since == -inf else '{0:.2f}'.format(self.since),
                '' if self.until == +inf else '{0:.2f}'.format(self.until)])
        string += '>'
        return string


class Segment(namedtuple('Segment', ['value', 'velocity', 'since', 'until'])):

    def __new__(cls, value, velocity, since=-inf, until=+inf):
        value = float(value)
        velocity = float(velocity)
        return super(Segment, cls).__new__(cls, value, velocity, since, until)

    def get(self, at=None):
        """Returns the value at the given time.

        :raises ValueError: the given time is out of the time range.
        """
        at = now_or(at)
        if not self.since <= at <= self.until:
            raise ValueError('Out of the time range: {0:.2f}~{1:.2f}'
                             ''.format(self.since, self.until))
        return self.value + self.velocity * (at - self.since)

    def guess(self, at=None):
        """Same with :meth:`get` but it returns the first or last value if the
        given time is out of the time range.
        """
        at = now_or(at)
        if at < self.since:
            return self.value
        elif self.until < at:
            return self.get(self.until)
        else:
            return self.get(at)

    def intersection(self, seg):
        """Gets the intersection with the given segment.

        :raises ValueError: there's no intersection.
        """
        # y-intercepts
        y_intercept = (self.value - self.velocity * self.since)
        seg_y_intercept = (seg.value - seg.velocity * seg.since)
        try:
            time = (seg_y_intercept - y_intercept) / \
                   (self.velocity - seg.velocity)
        except ZeroDivisionError:
            raise ValueError('Parallel segment')
        since = max(self.since, seg.since)
        until = min(self.until, seg.until)
        if since <= time <= until:
            pass
        else:
            raise ValueError('Intersection not in the time range')
        value = self.get(time)
        return (time, value)


class Boundary(object):

    #: The current segment.  To select next segment, call :meth:`walk`.
    seg = None

    #: The segment iterator.
    segs_iter = None

    #: Compares two values.  Choose one of `operator.lt` and `operator.gt`.
    cmp = None

    #: Returns the best value in an iterable or arguments.  It is indicated
    #: from :attr:`cmp` function.  `operator.lt` indicates :func:`min` and
    #: `operator.gt` indicates :func:`max`.
    best = None

    def __init__(self, segs_iter, cmp=operator.lt):
        assert cmp in [operator.lt, operator.gt]
        self.segs_iter = segs_iter
        self.cmp = cmp
        self.best = {operator.lt: min, operator.gt: max}[cmp]
        self.walk()

    def walk(self):
        """Choose the next segment."""
        self.seg = next(self.segs_iter)

    def cmp_eq(self, x, y):
        return x == y or self.cmp(x, y)

    def cmp_inv(self, x, y):
        return not self.cmp_eq(x, y)
