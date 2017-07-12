cdef:
    # events:
    int NONE, ADD, REMOVE
    # indices:
    int TIME, VALUE
    # strategies to control modification to out of the limits:
    int ERROR, OK, ONCE, CLAMP
    # numbers:
    double INF
