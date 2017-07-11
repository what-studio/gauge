from gauge.deterministic cimport Determination


cdef class Gauge:

    #: The time at the base.
    cdef double _base_time
    #: The value at the base.
    cdef double _base_value
    #: A sorted list of momenta.  The items are :class:`Momentum` objects.
    cdef momenta
    #: The constant maximum value.
    cdef double _max_value
    #: The gauge to indicate maximum value.
    cdef Gauge _max_gauge
    #: The constant minimum value.
    cdef double _min_value
    #: The gauge to indicate minimum value.
    cdef Gauge _min_gauge

    # internal attributes:
    cdef Determination _determination
    cdef _events
    cdef _limited_gauges

    cdef list momentum_events(self)


cdef class Momentum:
    cdef double velocity
    cdef double since
    cdef double until
