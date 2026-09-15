from retroui.core.layout import distribute


def test_empty():
    assert distribute(10, []) == []


def test_sum_is_exact_with_stretch():
    items = [(1, 3, 1), (2, 2, 2), (0, 5, 1)]
    for total in range(0, 60):
        sizes = distribute(total, items, spacing=1)
        assert all(s >= 0 for s in sizes)
        # min 합(3)보다 작을 때는 뒤에서부터 줄여서, 클 때는 stretch 로 채워서 항상 정확히 맞는다
        assert sum(sizes) == max(0, total - 2)


def test_pref_is_filled_before_stretch():
    assert distribute(10, [(0, 4, 0), (0, 2, 1)]) == [4, 6]


def test_pref_growth_is_proportional():
    assert distribute(6, [(0, 4, 0), (0, 8, 0)]) == [2, 4]


def test_stretch_ratio():
    assert distribute(30, [(0, 0, 1), (0, 0, 2)]) == [10, 20]


def test_remainder_goes_to_front_on_ties():
    assert distribute(10, [(0, 0, 1)] * 3) == [4, 3, 3]


def test_shrink_below_min_cuts_from_the_end():
    assert distribute(5, [(4, 4, 0), (4, 4, 0)]) == [4, 1]
    assert distribute(0, [(4, 4, 0), (4, 4, 0)]) == [0, 0]


def test_no_stretch_leaves_space():
    assert distribute(20, [(2, 5, 0)]) == [5]
