# -*- coding: utf-8 -*-
"""
   gauge.constants
   ~~~~~~~~~~~~~~~

   The constants which are used by the gauge implementation.

   :copyright: (c) 2013-2017 by What! Studio
   :license: BSD, see LICENSE for more details.

"""
cdef:

    # events:
    int NONE = 0
    int ADD = 1
    int REMOVE = 2

    # indices:
    int TIME = 0
    int VALUE = 1

    # strategies to control modification to out of the limits:
    int ERROR = 0
    int OK = 1
    int ONCE = 2
    int CLAMP = 3

    # numbers:
    double INF = float('inf')
