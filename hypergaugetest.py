from gauge import Gauge


g = Gauge(12, 100, at=0)
g.add_momentum(+1, since=1, until=6)
g.add_momentum(-1, since=3, until=8)


def test_case1():
    g.max = Gauge(15, 15, at=0)
    g.max.add_momentum(-1, until=5)
    assert g.determine2() == [
        (1, 12),
        (2, 13),
        (3, 12),
        (5, 10),
        (6, 10),
        (8, 8),
    ]


def test_case2():
    g.max = Gauge(15, 15, at=0)
    g.max.add_momentum(-1, until=4)
    g.max.add_momentum(+1, since=4, until=6)
    assert g.determine2() == [
        (1, 12),
        (2, 13),
        (3, 12),
        (4, 11),
        (6, 11),
        (8, 9),
    ]


def test_case3():
    g.set_max(10, at=0)
    assert g.determine2() == [
        (1, 12),
        (3, 12),
        (5, 10),
        (6, 10),
        (8, 8),
    ]
    g.set_max(Gauge(10, 100, at=0), at=0)
    assert g.determine2() == [
        (1, 12),
        (3, 12),
        (5, 10),
        (6, 10),
        (8, 8),
    ]


def test_case4():
    g.max = Gauge(15, 15, at=0)
    g.max.add_momentum(-1)
    assert g.determine2() == [
        (1, 12),
        (2, 13),
        (3, 12),
        (6, 9),
        (8, 7),
        (15, 0),
    ]
