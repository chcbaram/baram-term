import pytest

from retroui import App, HSplit, Label, VBox, VSplit
from retroui.input.events import MouseEvent


@pytest.fixture
def app():
    try:
        a = App(headless=True, size=(30, 20), theme="dos_blue")
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))
    yield a
    a.close()


def setup(app):
    top, bottom = Label("top"), Label("bottom")
    changes = []
    split = VSplit(top, bottom, ratio=0.5, min_top=3, min_bottom=4, on_change=changes.append)
    app.set_root(VBox(split))
    app.step()
    return split, top, bottom, changes


def drag(app, y0, y1, x=1):
    app.dispatch(MouseEvent("down", 1, x, y0, 0, 0))
    app.dispatch(MouseEvent("move", 0, x, y1, 0, 0))
    app.dispatch(MouseEvent("up", 1, x, y1, 0, 0))
    app.step()


def test_layout_follows_ratio(app):
    split, top, bottom, _ = setup(app)
    assert (top.rect.h, bottom.rect.y, bottom.rect.h) == (10, 10, 10)


def test_drag_either_boundary_row_moves_split(app):
    split, top, bottom, changes = setup(app)
    drag(app, 9, 5)  # 위 위젯의 마지막 줄을 잡고 4줄 위로
    assert top.rect.h == 6 and bottom.rect.y == 6 and changes == [0.3]
    drag(app, 6, 8)  # 아래 위젯의 첫 줄을 잡고 2줄 아래로
    assert top.rect.h == 8 and changes[-1] == 0.4


def test_min_heights_and_double_click_reset(app):
    split, top, bottom, changes = setup(app)
    drag(app, 9, 0)
    assert top.rect.h == 3
    drag(app, 2, 19)
    assert bottom.rect.h == 4
    y = split.split_y
    for _ in range(2):  # 더블클릭
        app.dispatch(MouseEvent("down", 1, 1, y, 0, 0))
        app.dispatch(MouseEvent("up", 1, 1, y, 0, 0))
    app.step()
    assert split.ratio == 0.5 and top.rect.h == 10 and changes[-1] == 0.5


def test_hidden_bottom_gives_all_rows_and_no_handle(app):
    split, top, bottom, changes = setup(app)
    bottom.visible = False
    app.step()
    assert top.rect.h == 20
    drag(app, 9, 3)
    assert top.rect.h == 20 and changes == []


def test_cursor_on_boundary_rows(app):
    split, top, bottom, _ = setup(app)
    assert app.cursor_name(top, 1, 9) == "resize_ns"
    assert app.cursor_name(bottom, 1, 10) == "resize_ns"
    assert app.cursor_name(top, 1, 4) is None
    assert app.cursor_name(bottom, 1, 15) is None


def hsetup(app):
    left, right = Label("left"), Label("right")
    changes = []
    split = HSplit(left, right, ratio=0.5, min_left=6, min_right=8, on_change=changes.append)
    app.set_root(VBox(split))
    app.step()
    return split, left, right, changes


def hdrag(app, x0, x1, y=1):
    app.dispatch(MouseEvent("down", 1, x0, y, 0, 0))
    app.dispatch(MouseEvent("move", 0, x1, y, 0, 0))
    app.dispatch(MouseEvent("up", 1, x1, y, 0, 0))
    app.step()


def test_hsplit_layout_and_drag(app):
    split, left, right, changes = hsetup(app)
    assert (left.rect.w, right.rect.x, right.rect.w) == (15, 15, 15)
    hdrag(app, 14, 10)  # 왼쪽 위젯의 마지막 칸을 잡고 4칸 왼쪽으로
    assert left.rect.w == 11 and right.rect.x == 11 and changes == [11 / 30]
    hdrag(app, 11, 13)  # 오른쪽 위젯의 첫 칸을 잡고 2칸 오른쪽으로
    assert left.rect.w == 13


def test_hsplit_min_widths_and_cursor(app):
    split, left, right, changes = hsetup(app)
    hdrag(app, 14, 0)
    assert left.rect.w == 6
    hdrag(app, 6, 29)
    assert right.rect.w == 8
    assert app.cursor_name(left, split.split_x - 1, 1) == "resize_ew"
    assert app.cursor_name(right, split.split_x, 1) == "resize_ew"
    assert app.cursor_name(left, 2, 1) is None


def test_hsplit_hidden_right_gives_all_columns(app):
    split, left, right, changes = hsetup(app)
    right.visible = False
    app.step()
    assert left.rect.w == 30
    hdrag(app, 14, 8)
    assert left.rect.w == 30 and changes == []
