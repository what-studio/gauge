# -*- coding: utf-8 -*-
"""
    gauge.common
    ~~~~~~~~~~~~

    The common components such as constants or utility functions.

    :copyright: (c) 2013-2015 by What! Studio
    :license: BSD, see LICENSE for more details.
"""
from time import time as now
import warnings


__all__ = ['ADD', 'REMOVE', 'TIME', 'VALUE', 'ERROR', 'OK', 'ONCE', 'CLAMP',
           'inf', 'now_or', 'deprecate']


# events.
ADD = 0
REMOVE = 1


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


def deprecate(message, *args, **kwargs):
    warnings.warn(DeprecationWarning(message.format(*args, **kwargs)))
