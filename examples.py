# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
import time

from gauge import Gauge, Discrete, Linear
from gauge.effect import GRAVITY_INTERVAL, Effect
from gauge.gravity import Gravity


class Energy(Gauge):

    min = 0
    max = 10
    gravity = Discrete(1, 5)  # +1 energy per 10 seconds


class Energy2(Gauge):

    min = 0
    max = 10
    gravity = Discrete(-1, 5)  # +1 energy per 10 seconds


class Life(Gauge):

    min = 0
    max = 10
    gravity = Linear(-0.5, 1)  # +1 energy per 10 seconds


e = Energy()
e2 = Energy2(0)
l = Life(Life.max)

_5sec_later = datetime.utcnow() + timedelta(0, 5)
e = Energy(2)
e.effects.append(Effect(Gravity(1, 10), until=_5sec_later))
for x in e.gravities_effected():
    print x
while 1:
    print e
    time.sleep(1)
