# -*- coding: utf-8 -*-
"""
   gauge.common
   ~~~~~~~~~~~~

   The common components such as constants or utility functions.

   :copyright: (c) 2013-2017 by What! Studio
   :license: BSD, see LICENSE for more details.

"""
from time import time as now


__all__ = ['NONE', 'ADD', 'REMOVE', 'TIME', 'VALUE', 'ERROR', 'OK', 'ONCE',
           'CLAMP', 'inf', 'now_or']


# events.
NONE = 0
ADD = 1
REMOVE = 2


# indices.
TIME = 0
VALUE = 1


# strategies to control modification to out of the limits.
ERROR = 0
OK = 1
ONCE = 2
CLAMP = 3


inf = float('inf')


def now_or(time):
    """Returns the current time if `time` is ``None``."""
    return now() if time is None else float(time)
