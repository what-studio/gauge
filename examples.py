# -*- coding: utf-8 -*-
from gauge import Gauge, Stairs, Linear


class Energy(Gauge):

    min = 0
    max = 10
    base = 10
    gravity = Stairs(1, 5)  # +1 energy per 10 seconds


e = Energy()
