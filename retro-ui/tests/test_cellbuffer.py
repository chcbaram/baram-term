from retroui.core.geometry import Rect
from retroui.render.cellbuffer import WIDE_CONT, CellBuffer

FG = (255, 255, 255)
BG = (0, 0, 170)


def make(cols=10, rows=2):
    return CellBuffer(cols, rows, FG, BG)


def test_text_places_wide_char_in_two_cells():
    b = make()
    assert b.text(0, 0, "a한b", FG, BG) == 4
    assert b.get(1, 0)[0] == "한"
    assert b.get(2, 0)[0] == WIDE_CONT
    assert b.row_text(0) == "a한b" + " " * 6


def test_overwrite_lead_half_clears_tail():
    b = make()
    b.text(0, 0, "한", FG, BG)
    b.put(0, 0, "x", FG, BG)
    assert b.row_text(0).startswith("x ")
    assert b.get(1, 0)[0] == " "


def test_overwrite_tail_half_clears_lead():
    b = make()
    b.text(0, 0, "한", FG, BG)
    b.put(1, 0, "x", FG, BG)
    assert b.row_text(0).startswith(" x")


def test_wide_char_at_right_clip_becomes_space():
    b = make()
    b.text(8, 0, "a한", FG, BG)
    assert b.row_text(0)[8:] == "a "


def test_wide_char_straddling_left_clip_becomes_space():
    b = make()
    b.text(0, 0, "#" * 10, FG, BG)
    b.text(0, 0, "한a", FG, BG, clip=Rect(1, 0, 5, 1))
    assert b.row_text(0) == "# a#######"


def test_fill_breaks_wide_chars_at_edges():
    b = make()
    b.text(0, 0, "가나다", FG, BG)
    b.fill(Rect(1, 0, 2, 1), "-", FG, BG)
    assert b.row_text(0) == " -- 다" + " " * 4


def test_changed_runs_and_commit():
    b = make()
    assert list(b.changed_runs()) == [(0, 0, 10), (1, 0, 10)]
    b.commit()
    assert list(b.changed_runs()) == []

    b.text(3, 1, "ok", FG, BG)
    assert list(b.changed_runs()) == [(1, 3, 5)]
    b.commit()

    b.put(5, 0, "가", FG, BG)
    assert list(b.changed_runs()) == [(0, 5, 7)]
    b.commit()

    # 같은 내용을 다시 써도 변경 구간은 없다
    b.put(5, 0, "가", FG, BG)
    assert list(b.changed_runs()) == []


def test_color_change_is_a_change():
    b = make()
    b.commit()
    b.put(0, 0, " ", FG, (1, 2, 3))
    assert list(b.changed_runs()) == [(0, 0, 1)]


def test_resize_invalidates_everything():
    b = make()
    b.commit()
    b.resize(4, 3)
    assert list(b.changed_runs()) == [(0, 0, 4), (1, 0, 4), (2, 0, 4)]
