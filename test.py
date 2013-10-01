# -*- coding: utf-8 -*-
from contextlib import contextmanager
from datetime import datetime

from freezegun import freeze_time

from gauge import Gauge, Stairs, Linear


@contextmanager
def t(timestamp):
    time_freezer = freeze_time('', 0)
    time_freezer.time_to_freeze = datetime.fromtimestamp(timestamp)
    with time_freezer:
        yield


class Energy(Gauge):

    min = 0
    max = 10
    base = 10
    gravity = Stairs(1, 10)  # +1 energy per 10 seconds

    def use(self, amount=1, at=None):
        return self.decr(amount, at)

    def recover_in(self, at=None):
        return self.gravity.apply_in(self, at)


class Life(Gauge):

    min = 0
    max = 100
    base = 0
    gravity = Linear(-1, 10)  # -1 life per 10 seconds

    def recover(self, amount=1, at=None):
        return self.incr(amount, at)

    def hurt(self, amount=1, at=None):
        return self.decr(amount, at)


def test_energy():
    with t(0):
        energy = Energy()
        assert energy == 10  # maximum by the default
        energy.use()
        assert energy == 9
        assert energy.recover_in() == 10
    with t(0.5):
        assert energy == 9
        assert energy.recover_in() == 9.5
    with t(1):
        assert energy == 9
        assert energy.recover_in() == 9
    with t(2):
        assert energy == 9
        assert energy.recover_in() == 8
    with t(9):
        assert energy == 9
        assert energy.recover_in() == 1
    with t(10):
        assert energy == 10  # recovered fully
        assert energy.recover_in() is None
    with t(20):
        assert energy == 10  # no more recovery
        energy.incr(20, limit=False)
        assert energy == 30  # extra 20 energy
    with t(100):
        assert energy == 30


def _test_life():
    with t(0):
        life = Life()
        assert life == 100
    with t(1):
        assert life == 99.9
    with t(2):
        assert life == 99.8
    with t(10):
        assert life == 99
    with t(100):
        assert life == 90
        life.recover(1000)
        assert life == 100  # limited by the maximum
