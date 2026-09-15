from retroui.core.geometry import Rect


def area(rects):
    return sum(r.w * r.h for r in rects)


def test_intersect_and_union():
    a = Rect(0, 0, 10, 10)
    b = Rect(5, 5, 10, 10)
    assert a.intersect(b) == Rect(5, 5, 5, 5)
    assert a.union(b) == Rect(0, 0, 15, 15)
    assert a.intersect(Rect(20, 20, 1, 1)).empty


def test_subtract_hole_in_middle():
    base = Rect(0, 0, 10, 10)
    hole = Rect(2, 3, 4, 5)
    parts = base.subtract(hole)
    assert len(parts) == 4
    assert area(parts) == 100 - 20
    for i, p in enumerate(parts):
        assert not p.intersects(hole)
        for q in parts[i + 1 :]:
            assert not p.intersects(q)


def test_subtract_edge_cases():
    base = Rect(0, 0, 10, 10)
    assert base.subtract(Rect(50, 50, 5, 5)) == [base]
    assert base.subtract(Rect(-1, -1, 20, 20)) == []
    assert area(base.subtract(Rect(0, 0, 10, 4))) == 60


def test_inset():
    assert Rect(0, 0, 10, 5).inset(1) == Rect(1, 1, 8, 3)
    assert Rect(0, 0, 2, 2).inset(3) == Rect(3, 3, 0, 0)
