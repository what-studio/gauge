# -*- coding: utf-8 -*-
"""
   gauge
   ~~~~~

   Deterministic linear gauge library.

   :copyright: (c) 2013-2017 by What! Studio
   :license: BSD, see LICENSE for more details.

"""
from __future__ import absolute_import

from gauge.__about__ import __version__  # noqa
from gauge.constants import CLAMP, ERROR, OK, ONCE
from gauge.core import Gauge, Momentum


__all__ = ['Gauge', 'Momentum', 'ERROR', 'OK', 'ONCE', 'CLAMP']


try:
    import __pypy__
except ImportError:
    pass
else:
    # Here's a workaround which makes :class:`Gauge` be picklable in PyPy.
    # ``Gauge.__module__`` and ``__name__`` should be ``'gauge.core'`` and
    # ``'Gauge'``.  But in PyPy, unlike CPython, they are ``'gauge'`` and
    # ``'core.Gauge'``.
    locals()['core.Gauge'] = Gauge
    del __pypy__
