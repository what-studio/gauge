from gauge import Gauge, now_or


class Equilibrium(object):

    gauge = None
    speed = None

    def __init__(self, medium, speed):
        self.speed = speed
        self.medium = medium

    @property
    def medium(self):
        return self._medium

    @medium.setter
    def medium(self, medium, at=None):
        at = now_or(at)
        self._medium = medium
        if self.gauge is None:
            self.gauge = Gauge(medium, medium, medium)
            return
        value = self.gauge.clear_momenta(at)
        if value == medium:
            self.gauge._set_limits(medium, medium, at=at)
            return
        if value < medium:
            self.gauge.set_max(medium, at=at)
            velocity = +self.speed
        elif value > medium:
            self.gauge.set_min(medium, at=at)
            velocity = -self.speed
        self.gauge.add_momentum(velocity, since=at)


if __name__ == '__main__':
    import time
    import signal
    eq = Equilibrium(0, 1)
    def set_medium(*__):
        medium = raw_input('New medium: ')
        eq.medium = float(medium)
    signal.signal(signal.SIGQUIT, set_medium)
    while True:
        print eq.gauge.current()
        time.sleep(0.5)
