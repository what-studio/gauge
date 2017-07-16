# -*- coding: utf-8 -*-
"""
   gauge.constants
   ~~~~~~~~~~~~~~~

   The constants which are used by the gauge implementation.

   :copyright: (c) 2013-2017 by What! Studio
   :license: BSD, see LICENSE for more details.

"""
__all__ = ['NONE', 'ADD', 'REMOVE', 'ERROR', 'OK', 'ONCE', 'CLAMP', 'inf']


cdef:

    # events:
    int EV_NONE = 0
    int EV_ADD = 1
    int EV_REMOVE = 2

    # strategies to control modification to out of the limits:
    int LI_ERROR = 0
    int LI_OK = 1
    int LI_ONCE = 2
    int LI_CLAMP = 3

    # numbers:
    double INF = float('inf')


NONE = EV_NONE
ADD = EV_ADD
REMOVE = EV_REMOVE

ERROR = LI_ERROR
OK = LI_OK
ONCE = LI_ONCE
CLAMP = LI_CLAMP

inf = INF


cdef inline str CLASS_NAME(obj):
    __, __, name = obj.__class__.__name__.rpartition('.')
    return name
