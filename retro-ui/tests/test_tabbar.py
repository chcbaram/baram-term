import pytest

from retroui import App, Label, TabBar, VBox
from retroui.input.events import MouseEvent
from retroui.widgets.tabbar import ADD


@pytest.fixture
def app():
    try:
        a = App(headless=True, size=(40, 6), theme="mono")
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))
    yield a
    a.close()


def setup(app, titles=("HEX", "boot", "sensor")):
    picked, added, menus = [], [], []
    bar = TabBar(titles, on_select=picked.append, on_add=lambda: added.append(True), on_menu=lambda i, x, y: menus.append((i, x, y)))
    app.set_root(VBox(bar, Label("below")))
    app.step()
    return bar, picked, added, menus


def click(app, x, y, button=1):
    app.dispatch(MouseEvent("down", button, x, y, 0, 0))
    app.dispatch(MouseEvent("up", button, x, y, 0, 0))


def span_of(bar, index):
    return next((start, end) for start, end, i in bar._spans if i == index)


def test_titles_separators_and_add_button(app):
    bar, *_ = setup(app)
    row = app.screen_text()[0]
    assert "HEX" in row and "boot" in row and "sensor" in row
    assert "│" in row and row.rstrip().endswith("+")
    assert bar.selected == 0


def test_selected_tab_is_highlighted(app):
    bar, picked, *_ = setup(app)
    pal = app.theme.palette
    start, _end = span_of(bar, 0)
    assert app.buf.get(bar.rect.x + start + 1, bar.rect.y)[2] == pal.sel_bg
    start1, _ = span_of(bar, 1)
    assert app.buf.get(bar.rect.x + start1 + 1, bar.rect.y)[2] != pal.sel_bg


def test_click_selects_and_keeps_focus_elsewhere(app):
    bar, picked, *_ = setup(app)
    app.set_focus(None)
    start, _ = span_of(bar, 2)
    click(app, bar.rect.x + start + 1, bar.rect.y)
    assert bar.selected == 2 and picked == [2]
    assert app.focus is None  # 탭은 포커스를 가져가지 않는다
    click(app, bar.rect.x + start + 1, bar.rect.y)
    assert picked == [2]  # 같은 탭을 다시 눌러도 신호는 한 번만


def test_plus_adds_and_right_click_opens_menu(app):
    bar, picked, added, menus = setup(app)
    start, _ = span_of(bar, ADD)
    click(app, bar.rect.x + start + 1, bar.rect.y)
    assert added == [True] and picked == []

    start1, _ = span_of(bar, 1)
    click(app, bar.rect.x + start1 + 1, bar.rect.y, button=3)
    assert menus and menus[0][0] == 1
    assert bar.selected == 0  # 오른쪽 클릭은 고르지 않는다


def test_tab_at_and_set_titles(app):
    bar, picked, *_ = setup(app)
    start, end = span_of(bar, 1)
    assert bar.tab_at(bar.rect.x + start) == 1 and bar.tab_at(bar.rect.x + end - 1) == 1
    assert bar.tab_at(bar.rect.x + span_of(bar, ADD)[0]) == ADD

    bar.set_titles(["one"], selected=0)
    app.step()
    assert bar.titles == ["one"] and bar.selected == 0
    assert "sensor" not in app.screen_text()[0]
    bar.set_titles([])
    app.step()
    assert bar.selected == -1 and app.screen_text()[0].strip().startswith("│")


def test_long_titles_are_truncated_but_plus_stays(app):
    bar, *_ = setup(app, titles=["boot sequence long", "sensor check long", "third long one"])
    app.step()
    row = app.screen_text()[0]
    assert row.rstrip().endswith("+")
    assert "boot sequence long" not in row  # 좁으면 줄여서 보여준다
    assert bar.tab_at(bar.rect.x + span_of(bar, ADD)[0]) == ADD
