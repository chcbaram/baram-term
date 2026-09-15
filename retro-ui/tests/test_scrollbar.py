import math

import pytest

from retroui import App, HBox, ScrollBar, Spacer, Terminal, VBox
from retroui.input.events import MouseEvent, WheelEvent


@pytest.fixture
def app():
    try:
        a = App(headless=True, size=(10, 8), theme="mono")
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))
    yield a
    a.close()


def place(app):
    sb = ScrollBar()
    app.set_root(HBox(Spacer(), sb))
    app.screen_text()
    return sb


def cell(app, sb, y):
    app.screen_text()
    return app.buf.get(sb.rect.x, y)


def py_for_eighth(app, y8):
    return math.ceil(y8 * app.fonts.ch / 8)


def mouse(app, kind, sb, py):
    app.dispatch(MouseEvent(kind, 0 if kind == "move" else 1, sb.rect.x, py // app.fonts.ch, 0, py))


def test_not_scrollable_draws_track_only(app):
    sb = place(app)
    sb.set_range(5, 8, 0)
    assert sb.thumb() is None
    assert all(cell(app, sb, y)[2] == app.theme.palette.grid for y in range(8))


def test_thumb_at_top_and_bottom(app):
    sb = place(app)
    pal = app.theme.palette
    sb.set_range(80, 8, 0)
    assert sb.thumb() == (0, 8)
    assert cell(app, sb, 0)[2] == pal.dim and cell(app, sb, 1)[2] == pal.grid
    sb.set_range(80, 8, 72)
    assert sb.thumb() == (56, 64)
    assert cell(app, sb, 7)[2] == pal.dim and cell(app, sb, 6)[2] == pal.grid


def test_thumb_ends_use_eighth_blocks(app):
    sb = place(app)
    pal = app.theme.palette
    sb.set_range(16, 8, 1)
    assert sb.thumb() == (4, 36)
    assert cell(app, sb, 0) == ("▄", pal.dim, pal.grid, 0)  # 아래 4/8 이 손잡이
    assert cell(app, sb, 1)[2] == pal.dim
    assert cell(app, sb, 4) == ("▄", pal.grid, pal.dim, 0)  # 위 4/8 이 손잡이, 아래 4/8 은 트랙


def test_click_track_pages_and_drag_moves_thumb(app):
    sb = place(app)
    moved = []
    sb.scrolled.connect(moved.append)
    sb.set_range(80, 8, 0)

    mouse(app, "down", sb, py_for_eighth(app, 5 * 8))  # 손잡이 아래 트랙
    mouse(app, "up", sb, py_for_eighth(app, 5 * 8))
    assert sb.pos == 8 and moved == [8]

    start, end = sb.thumb()
    grab = start + 2
    mouse(app, "down", sb, py_for_eighth(app, grab))
    mouse(app, "move", sb, py_for_eighth(app, grab + 64))  # 끝까지 끌기
    mouse(app, "up", sb, py_for_eighth(app, grab + 64))
    assert sb.pos == sb.max_pos == 72


def test_terminal_scrollbar_follows_scrollback(app):
    t = Terminal(scrollbar=True)
    t.wheel_lines = 3  # OS 마다 기본값이 달라서 아래 계산이 맞게 정해 둔다
    app.set_root(VBox(t))
    app.step()
    assert t.screen.cols == app.cols - 1
    for i in range(40):
        t.feed(f"line {i}\r\n")
    sb = t.scrollbar
    assert (sb.total, sb.page, sb.pos) == (41, 8, 33)

    # 손잡이는 맨 아래: 맨 위 트랙을 누르면 한 페이지 위로
    app.dispatch(MouseEvent("down", 1, sb.rect.x, 0, 0, 1))
    app.dispatch(MouseEvent("up", 1, sb.rect.x, 0, 0, 1))
    assert t.scroll_offset == 8 and sb.pos == 25
    assert app.focus is t  # 스크롤바를 눌러도 입력 포커스는 터미널

    app.dispatch(WheelEvent(0, -1, 0, 0, 0, 0))  # 휠 아래로
    assert sb.pos == 28 and t.scroll_offset == 5

    t.feed("more\r\n")  # 과거를 보는 중에는 보던 줄 유지, 스크롤바 전체 줄 수만 늘어난다
    assert sb.total == 42 and sb.pos == 28
