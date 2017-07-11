cdef class Determination(list):

    cdef:
        #: The time when the gauge starts to be in_range of the limits.
        double _in_range_since
        bint _in_range

    cdef void _determine(self, double time, double value, bint in_range=?)


cdef inline double SEGMENT_VALUE(double at,
                                 double time1, double time2,
                                 double value1, double value2):
    cdef double rate
    if at == time1:
        return value1
    elif at == time2:
        return value2
    else:
        rate = float(at - time1) / (time2 - time1)
        return value1 + rate * (value2 - value1)


cdef inline double SEGMENT_VELOCITY(double time1, double time2,
                                    double value1, double value2):
    return (value2 - value1) / (time2 - time1)
