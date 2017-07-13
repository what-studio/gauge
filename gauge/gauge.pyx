# -*- coding: utf-8 -*-
from __future__ import absolute_import

from bisect import bisect_right
from collections import namedtuple
import gc
import operator
from time import time as now
try:
    from weakref import WeakSet
except ImportError:
    from weakrefset import WeakSet

from six.moves import zip
from sortedcontainers import SortedList, SortedListWithKey

from gauge.__about__ import __version__  # noqa
from gauge.constants cimport (
    EV_ADD, EV_NONE, EV_REMOVE, INF, LI_CLAMP, LI_ERROR, LI_OK, LI_ONCE)
from gauge.deterministic cimport Determination, SEGMENT_VALUE, SEGMENT_VELOCITY


__all__ = ['Gauge', 'Momentum']


# indices:
DEF TIME = 0
DEF VALUE = 1


cdef by_until = operator.itemgetter(2)


cdef inline double NOW_OR(time):
    """Returns the current time if `time` is ``None``."""
    return now() if time is None else float(time)


cdef inline void RESTORE_INTO(Gauge gauge, (double, double) base, list momenta,
                              double max_value, Gauge max_gauge,
                              double min_value, Gauge min_gauge):
    gauge._base_time, gauge._base_value = base
    gauge._max_value, gauge._max_gauge = max_value, max_gauge
    gauge._min_value, gauge._min_gauge = min_value, min_gauge
    if max_gauge is not None:
        max_gauge._limited_gauges.add(gauge)
    if min_gauge is not None:
        min_gauge._limited_gauges.add(gauge)
    if momenta:
        gauge.add_momenta([gauge._make_momentum(*m) for m in momenta])


def restore_gauge(gauge_class, base, momenta, max_value,
                  max_gauge, min_value, min_gauge):
    """Restores a gauge from the arguments.  It is used for Pickling."""
    gauge = gauge_class.__new__(gauge_class)
    gauge.__preinit__()
    RESTORE_INTO(gauge, base, momenta, max_value,
                 max_gauge, min_value, min_gauge)
    return gauge


cdef class Gauge:
    """Represents a gauge.  A gauge has a value at any moment.  It can be
    modified by an user's adjustment or an effective momentum.
    """

    @property
    def base(self):
        return (self._base_time, self._base_value)

    @property
    def max_value(self):
        if self._max_gauge is None:
            return self._max_value

    @property
    def max_gauge(self):
        if self._max_gauge is not None:
            return self._max_gauge

    @property
    def min_value(self):
        if self._min_gauge is None:
            return self._min_value

    @property
    def min_gauge(self):
        if self._min_gauge is not None:
            return self._min_gauge

    def __init__(self, double value, max, min=0, at=None):
        self.__preinit__()
        at = NOW_OR(at)
        self._base_time, self._base_value = at, value
        self._set_range(max, min, at=at, _incomplete=True)

    def __preinit__(self):
        """Called by :meth:`__init__` and :meth:`__setstate__`."""
        self._max_gauge = self._min_gauge = None
        self.momenta = SortedListWithKey(key=by_until)
        self._determination = None
        self._events = SortedList()
        # a weak set of gauges that refer the gauge as a limit gauge.
        self._limited_gauges = WeakSet()

    @property
    def determination(self):
        """The cached determination.  If there's no the cache, it redetermines
        and caches that.

        A determination is a sorted list of 2-dimensional points which take
        times as x-values, gauge values as y-values.
        """
        if self._determination is None:
            # redetermine and cache.
            self._determination = Determination(self)
        return self._determination

    def invalidate(self):
        """Invalidates the cached determination.  If you touches the
        determination at the next first time, that will be redetermined.

        You don't need to call this method because all mutating methods such as
        :meth:`incr` or :meth:`add_momentum` calls it.

        :returns: whether the gauge is invalidated actually.
        """
        if self._determination is None:
            return False
        # remove the cached determination.
        self._determination = None
        # invalidate limited gauges together.
        cdef Gauge gauge
        for gauge in self._limited_gauges:
            gauge._limit_gauge_invalidated(self)
        return True

    def get_max(self, at=None):
        """Predicts the current maximum value."""
        if self._max_gauge is None:
            return self._max_value
        else:
            return self._max_gauge.get(at)

    def get_min(self, at=None):
        """Predicts the current minimum value."""
        if self._min_gauge is None:
            return self._min_value
        else:
            return self._min_gauge.get(at)

    #: The alias of :meth:`get_max`.
    max = get_max

    #: The alias of :meth:`get_min`.
    min = get_min

    def _set_range(self, max_=None, min_=None, at=None, _incomplete=False):
        at = NOW_OR(at)
        cdef:
            double forget_until = at
            double in_range_since
            Gauge limit_gauge
        # _incomplete=True when __init__() calls it.
        if not _incomplete:
            value = self.get(at)
            in_range_since = self.determination.in_range_since

        if max_ is not None:
            if self._max_gauge is not None:
                self._max_gauge._limited_gauges.discard(self)
            if isinstance(max_, Gauge):
                limit_gauge = max_
                limit_gauge._limited_gauges.add(self)
                self._max_gauge = limit_gauge
                self._max_value = limit_gauge.get(at)
                forget_until = min(forget_until, limit_gauge._base_time)
            else:
                self._max_gauge = None
                self._max_value = max_
            if not (_incomplete or in_range_since is None):
                value = min(value, self._max_value)

        if min_ is not None:
            if self._min_gauge is not None:
                self._min_gauge._limited_gauges.discard(self)
            if isinstance(min_, Gauge):
                limit_gauge = min_
                limit_gauge._limited_gauges.add(self)
                self._min_gauge = limit_gauge
                self._min_value = limit_gauge.get(at)
                forget_until = min(forget_until, limit_gauge._base_time)
            else:
                self._min_gauge = None
                self._min_value = min_
            if not (_incomplete or in_range_since is None):
                value = max(value, self._min_value)

        if _incomplete:
            return
        return self.forget_past(value, at=forget_until)

    def set_max(self, max, at=None):
        """Changes the maximum.

        :param max: a number or gauge to set as the maximum.
        :param at: the time to change.  (default: now)
        """
        return self._set_range(max_=max, at=at)

    def set_min(self, min, at=None):
        """Changes the minimum.

        :param min: a number or gauge to set as the minimum.
        :param at: the time to change.  (default: now)
        """
        return self._set_range(min_=min, at=at)

    def set_range(self, max=None, min=None, at=None):
        """Changes the both of maximum and minimum at once.

        :param max: a number or gauge to set as the maximum.  (optional)
        :param min: a number or gauge to set as the minimum.  (optional)
        :param at: the time to change.  (default: now)
        """
        return self._set_range(max, min, at=at)

    cdef (double, double) _predict(self, double at):
        """Predicts the current value and velocity.

        :param at: the time to observe.  (default: now)
        """
        cdef:
            Determination determination = self.determination
            double time1
            double time2
            double value
            double value1
            double value2
            double velocity
        if len(determination) == 1:
            # skip bisect_right() because it is expensive
            x = 0
        else:
            x = bisect_right(determination, (at, +INF))
        if x == 0:
            return (determination[0][VALUE], 0.)
        try:
            time2, value2 = determination[x]
        except IndexError:
            return (determination[-1][VALUE], 0.)
        time1, value1 = determination[x - 1]
        value = SEGMENT_VALUE(at, time1, time2, value1, value2)
        velocity = SEGMENT_VELOCITY(time1, time2, value1, value2)
        if determination.in_range_since is None:
            pass
        elif determination.in_range_since <= time1:
            value = self._clamp(value, at=at)
        return (value, velocity)

    def get(self, at=None):
        """Predicts the current value.

        :param at: the time to observe.  (default: now)
        """
        value, velocity = self._predict(NOW_OR(at))
        return value

    def velocity(self, at=None):
        """Predicts the current velocity.

        :param at: the time to observe.  (default: now)
        """
        value, velocity = self._predict(NOW_OR(at))
        return velocity

    def goal(self):
        """Predicts the final value."""
        return self.determination[-1][VALUE]

    def incr(self, delta, outbound=LI_ERROR, at=None):
        """Increases the value by the given delta immediately.  The
        determination would be changed.

        :param delta: the value to increase.
        :param outbound: the strategy to control modification to out of the
                         range.  (default: LI_ERROR)
        :param at: the time to increase.  (default: now)

        :raises ValueError: the value is out of the range.
        """
        at = NOW_OR(at)
        prev_value = self.get(at=at)
        value = prev_value + delta
        if outbound == LI_ONCE:
            outbound = LI_OK if self.in_range(at) else LI_ERROR
        if outbound != LI_OK:
            items = [(
                self.get_max, max, operator.gt,
                'the value to set is bigger than the maximum ({0} > {1})'
            ), (
                self.get_min, min, operator.lt,
                'the value to set is smaller than the minimum ({0} < {1})'
            )]
            for get_limit, clamp, cmp_, error_form in items:
                if not cmp_(delta, 0):
                    continue
                limit = get_limit(at)
                if not cmp_(value, limit):
                    continue
                if outbound == LI_ERROR:
                    raise ValueError(error_form.format(value, limit))
                elif outbound == LI_CLAMP:
                    value = clamp(prev_value, limit)
                    break
        return self.forget_past(value, at=at)

    def decr(self, delta, outbound=LI_ERROR, at=None):
        """Decreases the value by the given delta immediately.  The
        determination would be changed.

        :param delta: the value to decrease.
        :param outbound: the strategy to control modification to out of the
                         range.  (default: LI_ERROR)
        :param at: the time to decrease.  (default: now)

        :raises ValueError: the value is out of the range.
        """
        return self.incr(-delta, outbound=outbound, at=at)

    def set(self, value, outbound=LI_ERROR, at=None):
        """Sets the current value immediately.  The determination would be
        changed.

        :param value: the value to set.
        :param outbound: the strategy to control modification to out of the
                         range.  (default: LI_ERROR)
        :param at: the time to set.  (default: now)

        :raises ValueError: the value is out of the range.
        """
        at = NOW_OR(at)
        delta = value - self.get(at=at)
        return self.incr(delta, outbound=outbound, at=at)

    cdef double _clamp(self, double value, double at):
        max_ = self.get_max(at)
        if value > max_:
            return max_
        min_ = self.get_min(at)
        if value < min_:
            return min_
        return value

    def clamp(self, at=None):
        """Clamps the current value."""
        at = NOW_OR(at)
        value = self._clamp(self.get(at), at=at)
        return self.set(value, outbound=LI_OK, at=at)

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
        form = 'the gauge will not reach to {0}' + \
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

    def in_range(self, at=None):
        """Whether the gauge is between the range at the given time.

        :param at: the time to check.  (default: now)
        """
        in_range_since = self.determination.in_range_since
        if in_range_since is None:
            return False
        at = NOW_OR(at)
        return in_range_since <= at

    @staticmethod
    def _make_momentum(velocity_or_momentum, since=None, until=None):
        """Makes a :class:`Momentum` object by the given arguments.

        Override this if you want to use your own momentum class.

        :param velocity_or_momentum: a :class:`Momentum` object or just a
                                     number for the velocity.
        :param since: if the first argument is a velocity, it is the time to
                      start to affect the momentum.  (default: ``-INF``)
        :param until: if the first argument is a velocity, it is the time to
                      finish to affect the momentum.  (default: ``+INF``)

        :raises ValueError: `since` later than or same with `until`.
        :raises TypeError: the first argument is a momentum, but other
                           arguments passed.
        """
        cdef Momentum momentum
        if isinstance(velocity_or_momentum, Momentum):
            if not (since is None and until is None):
                raise TypeError('arguments behind the first argument as a '
                                'momentum should be None')
            momentum = velocity_or_momentum
        else:
            velocity = velocity_or_momentum
            if since is None:
                since = -INF
            if until is None:
                until = +INF
            momentum = Momentum(velocity, since, until)
        since, until = momentum.since, momentum.until
        if since == -INF or until == +INF or since < until:
            pass
        else:
            raise ValueError('\'since\' should be earlier than \'until\'')
        return momentum

    def add_momenta(self, momenta):
        """Adds multiple momenta."""
        cdef Momentum momentum
        for momentum in momenta:
            self.momenta.add(momentum)
            self._events.add((momentum.since, EV_ADD, momentum))
            if momentum.until != +INF:
                self._events.add((momentum.until, EV_REMOVE, momentum))
        self.invalidate()

    def remove_momenta(self, momenta):
        """Removes multiple momenta."""
        cdef Momentum momentum
        for momentum in momenta:
            try:
                self.momenta.remove(momentum)
            except ValueError:
                raise ValueError('{0} not in the gauge'.format(momentum))
            self._events.remove((momentum.since, EV_ADD, momentum))
            if momentum.until != +INF:
                self._events.remove((momentum.until, EV_REMOVE, momentum))
        self.invalidate()

    def add_momentum(self, *args, **kwargs):
        """Adds a momentum.  A momentum includes the velocity and the times to
        start to affect and to stop to affect.  The determination would be
        changed.

        All arguments will be passed to :meth:`_make_momentum`.

        :returns: a momentum object.  Use this to remove the momentum by
                  :meth:`remove_momentum`.

        :raises ValueError: `since` later than or same with `until`.
        """
        cdef Momentum momentum = self._make_momentum(*args, **kwargs)
        self.add_momenta([momentum])
        return momentum

    def remove_momentum(self, *args, **kwargs):
        """Removes the given momentum.  The determination would be changed.

        All arguments will be passed to :meth:`_make_momentum`.

        :raises ValueError: the given momentum not in the gauge.
        """
        cdef Momentum momentum = self._make_momentum(*args, **kwargs)
        self.remove_momenta([momentum])
        return momentum

    cpdef list momentum_events(self):
        """Yields momentum adding and removing events.  An event is a tuple of
        ``(time, EV_ADD|EV_REMOVE, momentum)``.
        """
        cdef:
            list events = []
            list remove = []
            Momentum momentum
            double time
            int method
        events.append((self._base_time, EV_NONE, None))
        momentum_ids = set([id(momentum) for momentum in self.momenta])
        for time, method, momentum in self._events:
            if id(momentum) not in momentum_ids:
                remove.append((time, method, momentum))
                continue
            events.append((time, method, momentum))
        for time, method, momentum in remove:
            self._events.remove((time, method, momentum))
        events.append((+INF, EV_NONE, None))
        return events

    def _rebase(self, value=None, at=None, remove_momenta_before=None):
        """Sets the base and removes momenta between indexes of ``start`` and
        ``stop``.

        :param value: the value to set coercively.  (default: the current
                      value)
        :param at: the time to set.  (default: now)
        :param remove_momenta_before: the stopping index of momentum removal.
                                      (default: the last)
        """
        at = NOW_OR(at)
        if value is None:
            value = self.get(at=at)
        for gauge in self._limited_gauges:
            gauge._limit_gauge_rebased(self, value, at=at)
        self._base_time, self._base_value = at, value
        del self.momenta[:remove_momenta_before]
        self.invalidate()
        return value

    def clear_momenta(self, value=None, at=None):
        """Removes all momenta.  The value is set as the current value.  The
        determination would be changed.

        :param value: the value to set coercively.
        :param at: the time base.  (default: now)
        """
        return self._rebase(value, at=at, remove_momenta_before=None)

    def forget_past(self, value=None, at=None):
        """Discards the momenta which doesn't effect anymore.

        :param value: the value to set coercively.
        :param at: the time base.  (default: now)
        """
        at = NOW_OR(at)
        x = self.momenta.bisect_left((-INF, -INF, at))
        return self._rebase(value, at=at, remove_momenta_before=x)

    def limited_gauges(self):
        gc.collect()
        return set(self._limited_gauges)

    def _limit_gauge_invalidated(self, limit_gauge):
        """The callback function which will be called at a limit gauge is
        invalidated.
        """
        self.invalidate()

    def _limit_gauge_rebased(self, limit_gauge, limit_value, at=None):
        """The callback function which will be called at a limit gauge is
        rebased.
        """
        at = max(NOW_OR(at), self._base_time)
        value = self.get(at)
        if self.in_range(at):
            clamp = {self._max_gauge: min, self._min_gauge: max}[limit_gauge]
            value = clamp(value, limit_value)
        self.forget_past(value, at=at)

    def __reduce__(self):
        cdef Momentum m
        return restore_gauge, (
            self.__class__,
            (self._base_time, self._base_value),
            [(m.velocity, m.since, m.until) for m in self.momenta],
            self._max_value, self._max_gauge,
            self._min_value, self._min_gauge
        )

    def _repr(self, at=None):
        """Example strings:

        - ``<Gauge 0.00/2.00>``
        - ``<Gauge 0.00 between 1.00~2.00>``
        - ``<Gauge 0.00 between <Gauge 0.00/2.00>~<Gauge 2.00/2.00>>``

        """
        cdef:
            Gauge limit_gauge
        at = NOW_OR(at)
        value = self.get(at=at)
        hyper = False
        limit_reprs = []
        limit_items = [(self._max_value, self._max_gauge),
                       (self._min_value, self._min_gauge)]
        for limit_value, limit_gauge in limit_items:
            if limit_gauge is None:
                limit_reprs.append('{0:.2f}'.format(limit_value))
            else:
                hyper = True
                limit_reprs.append('{0!r}'.format(limit_gauge))
        form = '<{0} {1:.2f}'
        if not hyper and self._min_value == 0:
            form += '/{2}>'
        else:
            form += ' between {3}~{2}>'
        return form.format(type(self).__name__, value, *limit_reprs)

    def __repr__(self):
        return self._repr()


cdef class Momentum:
    """A power of which increases or decreases the gauge continually between a
    specific period.
    """

    def __cinit__(self,
                  double velocity, double since=-INF, double until=+INF,
                  *args, **kwargs):
        self.velocity = float(velocity)
        self.since = since
        self.until = until

    def __getitem__(self, int index):
        if index == 0:
            return self.velocity
        elif index == 1:
            return self.since
        elif index == 2:
            return self.until
        else:
            raise IndexError

    def __len__(self):
        return 3

    def __iter__(self):
        return iter([self.velocity, self.since, self.until])

    def __hash__(self):
        return hash((self.velocity, self.since, self.until))

    def __richcmp__(self, other, int op):
        cdef tuple x = (self.velocity, self.since, self.until)
        cdef tuple y = tuple(other)
        if op == 0:
            return x < y
        elif op == 1:
            return x <= y
        elif op == 2:
            return x == y
        elif op == 3:
            return x != y
        elif op == 4:
            return x > y
        elif op == 5:
            return x >= y

    def __repr__(self):
        cdef str string
        string = '<{0} {1:+.2f}/s'.format(type(self).__name__, self.velocity)
        if self.since != -INF or self.until != +INF:
            string += ' ' + '~'.join([
                '' if self.since == -INF else '{0:.2f}'.format(self.since),
                '' if self.until == +INF else '{0:.2f}'.format(self.until)])
        string += '>'
        return string
