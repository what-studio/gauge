cdef class Determination(list):

    #: The time when the gauge starts to be in_range of the limits.
    cdef double _in_range_since
    cdef bint _in_range

    cdef void _determine(self, double time, double value, bint in_range=?)
