cdef class Determination(list):

    #: The time when the gauge starts to be in_range of the limits.
    cdef double _in_range_since
    cdef bint _in_range

    cdef void _determine(self, double time, double value, bint in_range=?)


cdef double _calc_segment_value(double at, double time1, double time2, double value1, double value2)
cdef double _calc_segment_velocity(double time1, double time2, double value1, double value2)
