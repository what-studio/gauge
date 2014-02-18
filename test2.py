from datetime import datetime, timedelta
#from pprint import pprint as pp
from gauge import Gauge

import matplotlib.pyplot as plt
import numpy as np


def later(seconds):
    return datetime.utcnow() + timedelta(0, seconds)


g = Gauge(1)
g.inertia(+0.5, until=later(20))
g.inertia(-2.5, since=later(10), until=later(15))
print g.current()

X = np.arange(600)
Y = []
Y_unlimited = []
now = datetime.utcnow()
for x in X:
    Y.append(g.current(now + timedelta(0, x / 10. - 5)))

ax = plt.subplot(111)
ax.set_ylim(-10, 20)
ax.plot(X, Y)

plt.show()
input()
