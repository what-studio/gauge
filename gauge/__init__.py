# -*- coding: utf-8 -*-
"""
    gauge
    ~~~~~

    Deterministic linear gauge library.

    :copyright: (c) 2013-2015 by What! Studio
    :license: BSD, see LICENSE for more details.
"""
from __future__ import absolute_import
from bisect import bisect_right
from collections import namedtuple
import operator
try:
    from weakref import WeakSet
except ImportError:
    from weakrefset import WeakSet

from six.moves import map, zip
from sortedcontainers import SortedList, SortedListWithKey

from .common import ADD, REMOVE, TIME, VALUE
from .common import ERROR, OK, ONCE, CLAMP, inf, now_or  # to export
from .deterministic import Determination, Segment


__version__ = '0.3.2'
__all__ = ['Gauge', 'Momentum',
           'ERROR', 'OK', 'ONCE', 'CLAMP', 'inf', 'now_or']


class Gauge(object):
    """Represents a gauge.  A gauge has a value at any moment.  It can be
    modified by an user's adjustment or an effective momentum.
    """

    #: The base time and value.
    base = (None, 0)

    #: A sorted list of momenta.  The items are :class:`Momentum` objects.
    momenta = None

    #: The constant maximum value.
    max_value = None

    #: The gauge to indicate maximum value.
    max_gauge = None

    #: The constant minimum value.
    min_value = None

    #: The gauge to indicate minimum value.
    min_gauge = None

    def __init__(self, value, max, min=0, at=None):
        self.__preinit__()
        at = now_or(at)
        self.base = (at, value)
        self._set_range(max, min, at=at, _incomplete=True)

    def __preinit__(self):
        """Called by :meth:`__init__` and :meth:`__setstate__`."""
        by_until = operator.itemgetter(2)
        self.momenta = SortedListWithKey(key=by_until)
        # momentum events.
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
        try:
            return self._determination
        except AttributeError:
            pass
        # redetermine and cache.
        self._determination = Determination(self)
        return self._determination

    def invalidate(self):
        """Invalidates the cached determination.  If you touches the
        determination at the next first time, that will be redetermined.

        You don't need to call this method because all mutating methods such as
        :meth:`incr` or :meth:`add_momentum` calls it.
        """
        # remove the cached determination.
        try:
            del self._determination
        except AttributeError:
            pass
        # invalidate limited gauges together.
        for gauge in self._limited_gauges:
            gauge._limit_gauge_invalidated(self)

    def get_max(self, at=None):
        """Predicts the current maximum value."""
        if self.max_gauge is None:
            return self.max_value
        else:
            return self.max_gauge.get(at)

    def get_min(self, at=None):
        """Predicts the current minimum value."""
        if self.min_gauge is None:
            return self.min_value
        else:
            return self.min_gauge.get(at)

    #: The alias of :meth:`get_max`.
    max = get_max

    #: The alias of :meth:`get_min`.
    min = get_min

    def _set_range(self, max_=None, min_=None, at=None, _incomplete=False):
        at = now_or(at)
        forget_until = at
        # _incomplete=True when __init__() calls it.
        if not _incomplete:
            value = self.get(at)
            in_range_since = self.determination.in_range_since
        items = [('max', max_, self.max_gauge, min),
                 ('min', min_, self.min_gauge, max)]
        for name, limit, prev_limit_gauge, clamp in items:
            if limit is None:
                continue
            if prev_limit_gauge is not None:
                # unlink from the previous limit gauge.
                prev_limit_gauge._limited_gauges.discard(self)
            if isinstance(limit, Gauge):
                limit_gauge, limit_value = limit, limit.get(at)
                forget_until = min(forget_until, limit_gauge.base[TIME])
            else:
                limit_gauge, limit_value = None, limit
            # set limit attrs
            value_attr, gauge_attr = name + '_value', name + '_gauge'
            if limit_gauge is None:
                setattr(self, value_attr, limit_value)
                setattr(self, gauge_attr, None)
            else:
                setattr(self, value_attr, None)
                setattr(self, gauge_attr, limit_gauge)
                limit_gauge._limited_gauges.add(self)
            if _incomplete or in_range_since is None:
                continue
            elif in_range_since <= at:
                value = clamp(value, limit_value)
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

    def _predict(self, at=None):
        """Predicts the current value and velocity.

        :param at: the time to observe.  (default: now)
        """
        at = now_or(at)
        determination = self.determination
        if len(determination) == 1:
            # skip bisect_right() because it is expensive
            x = 0
        else:
            x = bisect_right(determination, (at, +inf))
        if x == 0:
            return (determination[0][VALUE], 0.)
        try:
            time2, value2 = determination[x]
        except IndexError:
            return (determination[-1][VALUE], 0.)
        time1, value1 = determination[x - 1]
        value = Segment._calc_value(at, time1, time2, value1, value2)
        velocity = Segment._calc_velocity(time1, time2, value1, value2)
        if determination.in_range_since is None:
            pass
        elif determination.in_range_since <= time1:
            value = self._clamp(value, at=at)
        return (value, velocity)

    def get(self, at=None):
        """Predicts the current value.

        :param at: the time to observe.  (default: now)
        """
        value, velocity = self._predict(at)
        return value

    def velocity(self, at=None):
        """Predicts the current velocity.

        :param at: the time to observe.  (default: now)
        """
        value, velocity = self._predict(at)
        return velocity

    def goal(self):
        """Predicts the final value."""
        return self.determination[-1][VALUE]

    def incr(self, delta, outbound=ERROR, at=None):
        """Increases the value by the given delta immediately.  The
        determination would be changed.

        :param delta: the value to increase.
        :param outbound: the strategy to control modification to out of the
                         range.  (default: ERROR)
        :param at: the time to increase.  (default: now)

        :raises ValueError: the value is out of the range.
        """
        at = now_or(at)
        prev_value = self.get(at=at)
        value = prev_value + delta
        if outbound == ONCE:
            outbound = OK if self.in_range(at) else ERROR
        if outbound != OK:
            items = [(
                self.get_max, max, operator.gt,
                'The value to set is bigger than the maximum ({0} > {1})'
            ), (
                self.get_min, min, operator.lt,
                'The value to set is smaller than the minimum ({0} < {1})'
            )]
            for get_limit, clamp, cmp_, error_form in items:
                if not cmp_(delta, 0):
                    continue
                limit = get_limit(at)
                if not cmp_(value, limit):
                    continue
                if outbound == ERROR:
                    raise ValueError(error_form.format(value, limit))
                elif outbound == CLAMP:
                    value = clamp(prev_value, limit)
                    break
        return self.forget_past(value, at=at)

    def decr(self, delta, outbound=ERROR, at=None):
        """Decreases the value by the given delta immediately.  The
        determination would be changed.

        :param delta: the value to decrease.
        :param outbound: the strategy to control modification to out of the
                         range.  (default: ERROR)
        :param at: the time to decrease.  (default: now)

        :raises ValueError: the value is out of the range.
        """
        return self.incr(-delta, outbound=outbound, at=at)

    def set(self, value, outbound=ERROR, at=None):
        """Sets the current value immediately.  The determination would be
        changed.

        :param value: the value to set.
        :param outbound: the strategy to control modification to out of the
                         range.  (default: ERROR)
        :param at: the time to set.  (default: now)

        :raises ValueError: the value is out of the range.
        """
        at = now_or(at)
        delta = value - self.get(at=at)
        return self.incr(delta, outbound=outbound, at=at)

    def _clamp(self, value, at=None):
        at = now_or(at)
        max_ = self.get_max(at)
        if value > max_:
            return max_
        min_ = self.get_min(at)
        if value < min_:
            return min_
        return value

    def clamp(self, at=None):
        """Clamps the current value."""
        at = now_or(at)
        value = self._clamp(self.get(at), at=at)
        return self.set(value, outbound=OK, at=at)

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

    def in_range(self, at=None):
        """Whether the gauge is between the range at the given time.

        :param at: the time to check.  (default: now)
        """
        in_range_since = self.determination.in_range_since
        if in_range_since is None:
            return False
        at = now_or(at)
        return in_range_since <= at

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
        since, until = momentum.since, momentum.until
        self._events.remove((since, ADD, momentum))
        if until != +inf:
            self._events.remove((until, REMOVE, momentum))
        self.invalidate()
        return momentum

    def momentum_events(self):
        """Yields momentum adding and removing events.  An event is a tuple of
        ``(time, ADD|REMOVE, momentum)``.
        """
        yield (self.base[TIME], None, None)
        momentum_ids = set(id(m) for m in self.momenta)
        for time, method, momentum in list(self._events):
            if id(momentum) not in momentum_ids:
                self._events.remove((time, method, momentum))
                continue
            yield time, method, momentum
        yield (+inf, None, None)

    def _rebase(self, value=None, at=None, remove_momenta_before=None):
        """Sets the base and removes momenta between indexes of ``start`` and
        ``stop``.

        :param value: the value to set coercively.  (default: the current
                      value)
        :param at: the time to set.  (default: now)
        :param remove_momenta_before: the stopping index of momentum removal.
                                      (default: the last)
        """
        at = now_or(at)
        if value is None:
            value = self.get(at=at)
        for gauge in self._limited_gauges:
            gauge._limit_gauge_rebased(self, value, at=at)
        self.base = (at, value)
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
        at = now_or(at)
        x = self.momenta.bisect_left((-inf, -inf, at))
        return self._rebase(value, at=at, remove_momenta_before=x)

    def _limit_gauge_invalidated(self, limit_gauge):
        """The callback function which will be called at a limit gauge is
        invalidated.
        """
        self.invalidate()

    def _limit_gauge_rebased(self, limit_gauge, limit_value, at=None):
        """The callback function which will be called at a limit gauge is
        rebased.
        """
        at = max(now_or(at), self.base[TIME])
        value = self.get(at)
        if self.in_range(at):
            if limit_gauge is self.max_gauge:
                clamp = min
            elif limit_gauge is self.min_gauge:
                clamp = max
            else:
                raise ValueError('The limit is neither max nor min')
            value = clamp(value, limit_value)
        self.forget_past(value, at=at)

    def __getstate__(self):
        return (self.base, list(map(tuple, self.momenta)),
                self.max_value, self.max_gauge, self.min_value, self.min_gauge)

    def __setstate__(self, state):
        self.__preinit__()
        base, momenta, max_value, max_gauge, min_value, min_gauge = state
        self.base = base
        self.max_value, self.max_gauge = max_value, max_gauge
        self.min_value, self.min_gauge = min_value, min_gauge
        for limit_gauge in [max_gauge, min_gauge]:
            if limit_gauge is not None:
                limit_gauge._limited_gauges.add(self)
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
        limit_items = [(self.max_value, self.max_gauge),
                       (self.min_value, self.min_gauge)]
        for limit_value, limit_gauge in limit_items:
            if limit_gauge is None:
                limit_reprs.append('{0:.2f}'.format(limit_value))
            else:
                hyper = True
                limit_reprs.append('{0!r}'.format(limit_gauge))
        form = '<{0} {1:.2f}'
        if not hyper and self.min_value == 0:
            form += '/{2}>'
        else:
            form += ' between {3}~{2}>'
        return form.format(type(self).__name__, value, *limit_reprs)


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
