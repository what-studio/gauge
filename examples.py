# -*- coding: utf-8 -*-
from gauge import Gauge, Stairs, Linear


class Energy(Gauge):

    min = 0
    max = 10
    gravity = Stairs(1, 5)  # +1 energy per 10 seconds


class Energy2(Gauge):

    min = 0
    max = 10
    gravity = Stairs(-1, 5)  # +1 energy per 10 seconds


class Life(Gauge):

    min = 0
    max = 10
    gravity = Linear(-0.5, 1)  # +1 energy per 10 seconds


e = Energy()
e2 = Energy2(0)
l = Life(Life.max)
