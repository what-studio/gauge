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
from gauge.gauge import Gauge, Momentum


__all__ = ['Gauge', 'Momentum',
           'ERROR', 'OK', 'ONCE', 'CLAMP']
