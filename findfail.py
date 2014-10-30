import random
from random import Random
from gaugetest import assert_all_inside, random_gauge1, random_gauge2


maxint = 2 ** 64 / 2
x = 0
while True:
    # ---
    seed = random.randrange(maxint)
    g = random_gauge1(Random(seed))
    assert_all_inside(g, 'random_gauge1(R({0}))'.format(seed))
    # ---
    seed = random.randrange(maxint)
    g = random_gauge1(Random(seed), far=1000)
    assert_all_inside(g, 'random_gauge1(R({0}), far=1000)'.format(seed))
    # ---
    seed = random.randrange(maxint)
    g = random_gauge1(Random(seed), near=1e-10)
    assert_all_inside(g, 'random_gauge1(R({0}), near=1e-10)'.format(seed))
    # ---
    seed = random.randrange(maxint)
    g = random_gauge2(Random(seed), far=1e4)
    assert_all_inside(g, 'random_gauge2(R({0}), far=1e4)'.format(seed))
    x += 1
    if x % 1000 == 0:
        print x
