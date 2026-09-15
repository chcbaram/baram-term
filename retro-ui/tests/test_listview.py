import pygame
import pytest

from retroui import App, ListView, VBox
from retroui.input.events import Key, KeyEvent, Mod, MouseEvent, WheelEvent


@pytest.fixture
def app():
    try:
        a = App(headless=True, size=(40, 8), theme="mono")
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))
    yield a
    a.close()


def setup(app, items, details=None):
    lv = ListView(items, details)
    activated, selected = [], []
    lv.activated.connect(activated.append)
    lv.selection_changed.connect(selected.append)
    app.set_root(VBox(lv))
    app.set_focus(lv)
    app.step()
    return lv, activated, selected


def key(app, k, name=""):
    app.dispatch(KeyEvent(k, Mod.NONE, name))


def click(app, x, y):
    app.dispatch(MouseEvent("down", 1, x, y, 0, 0))
    app.dispatch(MouseEvent("up", 1, x, y, 0, 0))


def test_keys_move_selection_and_scroll(app):
    lv, activated, selected = setup(app, [f"item {i}" for i in range(30)])
    assert "item 0" in app.screen_text()[0]
    key(app, Key.DOWN)
    assert lv.selected == 1 and selected == [1]
    key(app, Key.END)
    assert lv.selected == 29 and lv.top == 30 - lv.rows
    assert "item 29" in app.screen_text()[-1]
    key(app, Key.HOME)
    assert lv.selected == 0 and lv.top == 0
    key(app, Key.PAGEDOWN)
    assert lv.selected == lv.rows - 1
    key(app, Key.RETURN)
    assert activated == [lv.selected]


def test_details_are_right_aligned_and_long_names_truncate(app):
    setup(app, ["short", "a" * 60], ["12K", "3M"])
    rows = app.screen_text()
    assert rows[0].rstrip().endswith("12K") and rows[0].startswith(" short")
    assert rows[1].rstrip().endswith("3M") and "aaaa" in rows[1]


def test_click_selects_and_double_click_activates(app):
    lv, activated, _ = setup(app, ["a", "b", "c"])
    click(app, 2, 2)
    assert lv.selected == 2 and activated == []
    click(app, 2, 2)
    assert activated == [2]


def test_type_ahead_cycles_through_matches(app):
    lv, _, _ = setup(app, ["apple", "banana", "blueberry", "cherry"])
    for expected in (1, 2, 1):
        app.dispatch(KeyEvent(pygame.K_b, Mod.NONE, "b"))
        assert lv.selected == expected


def test_wheel_scrolls_without_changing_selection(app):
    lv, _, selected = setup(app, [f"item {i}" for i in range(30)])
    app.dispatch(WheelEvent(0, -1, 2, 2, 0, 0))
    assert lv.top == 3 and lv.selected == 0 and selected == []
    assert lv.scrollbar.pos == 3


def test_set_items_keeps_index_in_range(app):
    lv, _, _ = setup(app, ["a", "b"])
    lv.set_items(["x"], selected=5)
    assert lv.selected == 0 and lv.current == "x"
    lv.set_items([])
    assert lv.selected == -1 and lv.current is None
