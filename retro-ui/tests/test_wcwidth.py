import unicodedata

from retroui.core.wcwidth import char_width, normalize, slice_cols, str_width, truncate


def test_ascii():
    assert str_width("abc 123") == 7


def test_hangul_is_two_cells():
    assert char_width("한") == 2
    assert str_width("한글 ok") == 7


def test_ambiguous_symbols_are_one_cell():
    for ch in "°±µΩ─│┌┼░█…":
        assert char_width(ch) == 1, ch


def test_zero_width():
    assert char_width("́") == 0  # combining acute
    assert char_width("​") == 0  # zero width space
    assert char_width("\n") == 0


def test_nfd_hangul_is_composed():
    nfd = unicodedata.normalize("NFD", "한글")
    assert len(nfd) == 6
    assert normalize(nfd) == "한글"
    assert str_width(nfd) == 4


def test_slice_cols_never_splits_wide_char():
    assert slice_cols("가나다", 1, 4) == " 나 "
    assert slice_cols("ab가c", 0, 3) == "ab "
    assert slice_cols("ab가c", 2, 2) == "가"
    assert slice_cols("abc", 5, 3) == ""


def test_truncate():
    assert truncate("abc", 5) == "abc"
    assert truncate("안녕하세요", 5) == "안녕…"
    assert str_width(truncate("안녕하세요", 6)) <= 6
    assert truncate("abc", 0) == ""
