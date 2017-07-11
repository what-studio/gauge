from gauge.deterministic cimport Determination


cdef class Gauge:

    cdef:
        #: The time at the base.
        double _base_time
        #: The value at the base.
        double _base_value
        #: The constant maximum value.
        double _max_value
        #: The gauge to indicate maximum value.
        Gauge _max_gauge
        #: The constant minimum value.
        double _min_value
        #: The gauge to indicate minimum value.
        Gauge _min_gauge
        #: A sorted list of momenta.  The items are :class:`Momentum` objects.
        public momenta

    # internal attributes:
    cdef:
        Determination _determination
        _events
        _limited_gauges

    cdef (double, double) _predict(self, double at)
    cdef double _clamp(self, double value, double at)

    cdef list momentum_events(self)


cdef class Momentum:

    cdef:
        public double velocity
        public double since
        public double until
