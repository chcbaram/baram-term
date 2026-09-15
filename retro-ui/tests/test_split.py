import pytest

from retroui import App, Label, VBox, VSplit
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
