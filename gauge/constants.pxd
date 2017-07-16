# -*- coding: utf-8 -*-


cdef:
    # events:
    int EV_NONE, EV_ADD, EV_REMOVE
    # strategies to control modification to out of the limits:
    int LI_ERROR, LI_OK, LI_ONCE, LI_CLAMP
    # numbers:
    double INF


cdef inline str CLASS_NAME(obj)
