from retroui.core.geometry import Rect
from retroui.render.cellbuffer import CellBuffer
from retroui.render.painter import Painter
from retroui.theme import BOX_SINGLE

FG = (255, 255, 255)
BG = (0, 0, 170)


def test_box_with_korean_title():
    buf = CellBuffer(12, 4, FG, BG)
    Painter(buf).box(Rect(0, 0, 12, 4), BOX_SINGLE, FG, BG, title="플롯")
    assert buf.text_lines() == [
        "┌┤ 플롯 ├──┐",
        "│          │",
        "│          │",
        "└──────────┘",
    ]


def test_sub_painter_translates_and_clips():
    buf = CellBuffer(10, 2, FG, BG)
    p = Painter(buf).sub(Rect(2, 1, 3, 1))
    assert p.text(0, 0, "abcdef", FG, BG) == 3
    p.text(0, -1, "zzz", FG, BG)  # 클립 밖 행
    assert buf.text_lines() == [" " * 10, "  abc     "]


def test_nested_sub_clip_is_intersection():
    buf = CellBuffer(10, 1, FG, BG)
    outer = Painter(buf).sub(Rect(1, 0, 4, 1))
    inner = outer.sub(Rect(2, 0, 10, 1))  # 부모 영역 밖으로 넘어가는 자식
    inner.text(0, 0, "xxxxxxxx", FG, BG)
    assert buf.row_text(0) == "   xx     "


def test_box_title_alignment():
    buf = CellBuffer(12, 3, FG, BG)
    Painter(buf).box(Rect(0, 0, 12, 3), BOX_SINGLE, FG, BG, title="Ab", title_align="right")
    assert buf.row_text(0) == "┌────┤ Ab ├┐"
    Painter(buf).box(Rect(0, 0, 12, 3), BOX_SINGLE, FG, BG, title="Ab", title_align="center")
    assert buf.row_text(0) == "┌──┤ Ab ├──┐"
    Painter(buf).box(Rect(0, 0, 12, 3), BOX_SINGLE, FG, BG, title="Ab")
    assert buf.row_text(0) == "┌┤ Ab ├────┐"


def test_right_aligned_wide_title():
    buf = CellBuffer(14, 3, FG, BG)
    Painter(buf).box(Rect(0, 0, 14, 3), BOX_SINGLE, FG, BG, title="포트", title_align="right")
    assert buf.row_text(0) == "┌────┤ 포트 ├┐"
