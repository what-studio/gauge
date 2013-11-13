# -*- coding: utf-8 -*-
from contextlib import contextmanager
from datetime import datetime
import math

from freezegun import freeze_time
import pytest

from gauge import Discrete, Gauge, Linear, now_or


@contextmanager
def t(timestamp):
    time_freezer = freeze_time('', 0)
    time_freezer.time_to_freeze = datetime.fromtimestamp(timestamp)
    with time_freezer:
        yield


def define_gauge(name, min, max, value_type=float):
    class TemporaryGauge(Gauge): pass
    TemporaryGauge.__name__ = name
    TemporaryGauge.min = min
    TemporaryGauge.max = max
    TemporaryGauge.value_type = value_type
    return TemporaryGauge


class Energy(Gauge):

    min = 0
    max = 10
    default_momentum = Discrete(+1, 10)  # +1 energy per 10 seconds
    value_type = int

    def use(self, amount=1, limit=True, at=None):
        return self.decr(amount, limit, at)

    def recover_in(self, at=None):
        return self.default_momentum.move_in(self, at)

    def recover_fully_in(self, at=None):
        """Calculates seconds to be recovered fully. If the energy is full or
        over the maximum, this returns ``None``.
        """
        recover_in = self.recover_in(at)
        if recover_in is None:
            return
        to_recover = self.max - self.current(at)
        return recover_in + self.default_momentum.interval * (to_recover - 1)

    def __repr__(self, at=None):
        at = now_or(at)
        momentum = self.default_momentum
        text = super(Energy, self).__repr__(at)
        recover_in = self.recover_in(at)
        if recover_in is None:
            return text
        sign = '+' if momentum.delta > 0 else ''
        seconds = int(math.ceil(recover_in))
        args = (sign, momentum.delta, seconds)
        return text[:-1] + ' {0}{1} in {2}s>'.format(*args)


class Life(Gauge):

    min = 0
    max = 100
    default_momentum = Linear(-1, 10)  # -1 life per 10 seconds

    def recover(self, amount=1, limit=True, at=None):
        return self.incr(amount, limit, at)

    def hurt(self, amount=1, limit=True, at=None):
        return self.decr(amount, limit, at)


def test_energy():
    with t(0):
        energy = Energy(Energy.max)
        assert energy == 10  # maximum by the default
        energy.use()
        assert energy == 9
        assert energy.recover_in() == 10
        assert energy.recover_fully_in() == 10
    with t(0.5):
        assert energy == 9
        assert energy.recover_in() == 9.5
        assert energy.recover_fully_in() == 9.5
    with t(1):
        assert energy == 9
        assert energy.recover_in() == 9
        assert energy.recover_fully_in() == 9
    with t(2):
        energy.use()
        assert energy == 8
        assert energy.recover_in() == 8
        assert energy.recover_fully_in() == 18
    with t(9):
        assert energy == 8
        assert energy.recover_in() == 1
        assert energy.recover_fully_in() == 11
    with t(10):
        assert energy == 9
        assert energy.recover_in() == 10
        assert energy.recover_fully_in() == 10
    with t(20):
        assert energy == 10
        energy.use(10)
        assert energy == 0
        with pytest.raises(ValueError):
            energy.use(1)
        energy.use(1, limit=False)
        assert energy == -1
        energy.incr(21, limit=False)
        assert energy == 20
    with t(100):
        assert energy == 20


def test_life():
    with t(0):
        life = Life(Life.max)
        assert life == 100
    with t(1):
        assert life == 99.9
    with t(2):
        assert life == 99.8
    with t(10):
        assert life == 99
    with t(100):
        assert life == 90
        with pytest.raises(ValueError):
            life.recover(1000)


def test_out_of_range():
    TemporaryGauge = define_gauge('TemporaryGauge', 0, 10, int)
    with t(0):
        rising = TemporaryGauge(5)
        rising.add_momentum(Discrete(+1, 1))
        falling = TemporaryGauge(5)
        falling.add_momentum(Discrete(-1, 1))
        assert rising == 5
        assert falling == 5
    with t(1):
        assert rising == 6
        assert falling == 4
    with t(4):
        assert rising == 9
        assert falling == 1
    with t(5):
        assert rising == 10
        assert falling == 0
    # no more movement
    with t(6):
        assert rising == 10
        assert falling == 0
    with t(10):
        with pytest.raises(ValueError):
            rising.incr(1)
        with pytest.raises(ValueError):
            falling.decr(1)
        rising.incr(1, limit=False)
        falling.decr(1, limit=False)
        assert rising == 11
        assert falling == -1
    # of course, more movement
    with t(11):
        assert rising == 11
        assert falling == -1
    with t(60):
        assert rising == 11
        assert falling == -1


def test_set_energy():
    with t(0):
        energy = Energy(Energy.max)
        energy.set(1)
        assert energy == 1
        energy.set(5)
        assert energy == 5


'''
def test_cast_energy():
    with t(0):
        true_energy = Energy(1)
        false_energy = Energy(0)
        assert int(true_energy) == 1
        assert int(false_energy) == 0
        assert float(true_energy) == 1.0
        assert float(false_energy) == 0.0
        assert bool(true_energy) is True
        assert bool(false_energy) is False
'''


def test_recover_energy():
    with t(0):
        energy = Energy(Energy.max)
        energy.use(2)
    with t(1):
        assert energy == 8
        assert energy.recover_in() == 9
        #assert energy.recover_fully_in() == 9
    with t(2):
        assert energy == 8
        assert energy.recover_in() == 8
        #assert energy.recover_fully_in() == 8
    with t(3):
        assert energy == 8
        assert energy.recover_in() == 7
        #assert energy.recover_fully_in() == 7
    with t(9):
        assert energy == 8
        assert energy.recover_in() == 1
        #assert energy.recover_fully_in() == 6
    with t(10):
        assert energy == 9
        assert energy.recover_in() == 10
        #assert energy.recover_fully_in() == 5
    with t(19):
        assert energy == 9
        assert energy.recover_in() == 1
        #assert energy.recover_fully_in() == 1
    with t(20):
        assert energy == 10
        assert energy.recover_in() == None
        #assert energy.recover_fully_in() == None
    with t(100):
        assert energy == 10
        assert energy.recover_in() == None
        #assert energy.recover_fully_in() == None

'''
def test_use_energy_while_recovering():
    energy = Energy(10, 5)
    with t(0):
        energy.use(5)
    with t(1):
        assert energy == 5
    with t(2):
        energy.use(1)
    with t(3):
        assert energy == 4
    with t(4):
        assert energy == 4
    with t(5):
        assert energy == 5
    with t(6):
        assert energy == 5
    with t(7):
        energy.use(1)
    with t(8):
        assert energy == 4
    with t(9):
        assert energy == 4
    with t(10):
        assert energy == 5


def test_use_energy_after_recovered():
    energy = Energy(10, 5)
    with t(0):
        energy.use(10)
    with t(1):
        assert energy == 0
    with t(5):
        energy.use(1)
    with t(6):
        assert energy == 0


def test_use_energy_at_the_future():
    energy = Energy(10, 5)
    with t(5):
        energy.use()
    with t(6):
        assert energy.passed() == 1
        with raises(ValueError):
        with t(4):
        energy.passed()
        with raises(ValueError):
        with t(3):
        energy.passed()
        with raises(ValueError):
        with t(2):
        energy.passed()
        with raises(ValueError):
        with t(1):
        energy.passed()
        with raises(ValueError):
        with t(0):
        energy.passed()


def test_future_tulerance():
    energy = Energy(10, 5, future_tolerance=4)
    with t(5):
        energy.use()
        # used at the past
    with t(6):
        assert energy.passed() == 1
        assert energy == 9
        # used at the near future
    with t(4):
        assert energy.passed() == 0
        assert energy == 9
    with t(3):
        assert energy.passed() == 0
        assert energy == 9
    with t(2):
        assert energy.passed() == 0
        assert energy == 9
    with t(1):
        assert energy.passed() == 0
        assert energy == 9
        # used at the remote future
    with t(0):
        with raises(ValueError):
            energy.passed()


def test_pickle_energy():
    try:
        import cPickle as pickle
    except ImportError:
        import pickle
    energy = Energy(10, 5)
    with t(0):
        assert energy == 10
    with t(1):
        energy.use(5)
    with t(2):
        assert energy == 5
        dump = pickle.dumps(energy)
        loaded_energy = pickle.loads(dump)
        assert energy == loaded_energy
    with t(3):
        assert energy == 5
    with t(3):
        assert loaded_energy == 5


class OldEnergy(Energy):

    def __setstate__(self):
        return (self.max, self.recovery_interval, self.recovery_quantity,
                self.used, self.used_at)


def test_pickle_energy_compatibility():
    try:
        import cPickle as pickle
    except ImportError:
        import pickle
    energy = OldEnergy(10, 5)
    with t(0):
        assert energy == 10
    with t(1):
        energy.use(5)
    with t(2):
        assert energy == 5
        dump = pickle.dumps(energy)
        dump = dump.replace('energytests\nOldEnergy'.encode(),
                            'energy\nEnergy'.encode())
        loaded_energy = pickle.loads(dump)
        assert type(loaded_energy) is Energy
    with t(3):
        assert energy == 5
    with t(3):
        assert loaded_energy == 5


def test_save_and_retrieve_energy():
    energy = Energy(10, 5)
    with t(0):
        assert energy == 10
    with t(1):
        energy.use(5)
    with t(2):
        assert energy == 5
    with t(3):
        saved = energy.used
        saved_used, saved_used_at = energy.used, energy.used_at
    with t(11):
        assert energy == 7
        loaded_energy = Energy(10, 5, used=saved_used, used_at=saved_used_at)
        assert loaded_energy == 7
        assert loaded_energy == energy
        loaded_energy2 = Energy(10, 5)
        loaded_energy2.used = saved_used
        loaded_energy2.used_at = saved_used_at
        assert loaded_energy2 == 7
        assert loaded_energy2 == energy
        loaded_energy3 = object.__new__(Energy)
        loaded_energy3.__init__(10, 5, used=saved_used, used_at=saved_used_at)
        assert loaded_energy3 == 7
        assert loaded_energy3 == energy
        loaded_energy4 = object.__new__(Energy)
        loaded_energy4.used = saved_used
        loaded_energy4.used_at = saved_used_at
        loaded_energy4.__init__(10, 5, used=saved_used, used_at=saved_used_at)
        assert loaded_energy4 == 7
        assert loaded_energy4 == energy


def test_float_recovery_interval():
    energy = Energy(10, 0.5)
    with t(0):
        energy == 10
    with t(1):
        energy.use(3)
    with t(2):
        energy == 9
    with t(3):
        energy == 10


def test_equivalent_energy():
    assert Energy(10, 10) == Energy(10, 10)
    assert Energy(5, 10) != Energy(10, 10)
    e1, e2, e3 = Energy(10, 10), Energy(10, 10), Energy(8, 10)
    with t(123):
        e1.use()
        e2.use()
        assert e1 == e2
    with t(128):
        e1.use()
        assert e1 != e2
        assert int(e1) == int(e3)
        assert e1 != e3


def test_set_max_energy():
    energy = Energy(10, 300)
    with t(0):
        assert energy == 10
    with t(1):
        energy.max = 11
    with t(2):
        assert energy == 11
    with t(3):
        energy.use()
    with t(4):
        assert energy == 10
    with t(5):
        energy.max = 12
    with t(6):
        assert energy == 10
    with t(7):
        energy.max = 9
    with t(8):
        assert energy == 9
    with t(9):
        energy.max = 1
    with t(10):
        assert energy == 1
    with t(11):
        energy.max = 10
    with t(12):
        assert energy == 10


def test_extra_energy():
    energy = Energy(10, 300)
    with t(0):
        energy.set(15)
    with t(1):
        assert energy == 15
        assert energy.recover_in() is None
        assert energy.recover_fully_in() is None
    with t(2):
        energy.use()
        assert energy.recover_in() is None
        assert energy.recover_fully_in() is None
    with t(6):
        energy.use(6)
    with t(7):
        assert energy.recover_in() == 299
        assert energy.recover_fully_in() == 599
    with t(8):
        assert energy.recover_in() == 298
        assert energy.recover_fully_in() == 598
    with t(9):
        energy.set(15)
        assert energy.recover_in() is None
        assert energy.recover_fully_in() is None
    with t(10):
        assert energy.recover_in() is None
        assert energy.recover_fully_in() is None


def test_repr_energy():
    energy = Energy(10, 300)
    with t(0):
        assert repr(energy) == '<Energy 10/10>'
    with t(1):
        energy.use()
    with t(2):
        assert repr(energy) == '<Energy 9/10 recover in 04:59>'


def test_compare_energy():
    energy = Energy(10, 300)
    with t(0):
        assert energy == 10
        assert energy > 9
        assert 9 < energy
        assert energy < 11
        assert 11 > energy
        assert 9 < energy < 11
        assert energy <= 10
        assert energy >= 10
        assert 10 <= energy
        assert 10 >= energy
        assert 10 <= energy <= 10


def test_arithmetic_assign_energy():
    energy = Energy(10, 3)
    with t(0):
        energy += 10
    with t(1):
        assert energy == 20
    with t(2):
        energy -= 13
    with t(3):
        assert energy == 7
    with t(6):
        assert energy == 8
    with t(7):
        energy += 10
    with t(8):
        energy -= 10;
    with t(9):
        assert energy.recover_in() == 2
    with t(10):
        assert energy.recover_in() == 1
    with t(11):
        assert energy == 9


def test_various_used_at():
    with t(2):
        energy = Energy(10, 3, used=1, used_at=1)
        assert energy == 9
    with t(5):
        assert energy == 10
    with t(2):
        energy = Energy(10, 3, used=1, used_at=datetime.utcfromtimestamp(1))
        assert energy == 9
    with t(5):
        assert energy == 10
'''
