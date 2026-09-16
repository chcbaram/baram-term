import pygame
import pytest

from retroui import App, Label, Menu, MenuBar, MenuItem, VBox
from retroui.input.events import Key, KeyEvent, Mod, MouseEvent
from retroui.widgets.menu import MenuPopup


@pytest.fixture
def app():
    try:
        a = App(headless=True, size=(60, 16), theme="mono")
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))
    yield a
    a.close()


def setup(app):
    picked = []
    panel = MenuItem(
        "Right panel",
        submenu=[
            MenuItem("HEX view", lambda: picked.append("hex"), key="H"),
            MenuItem("Memo", lambda: picked.append("memo"), key="T"),
        ],
    )
    bar = MenuBar([Menu("View", [MenuItem("Local echo", lambda: picked.append("echo")), panel])])
    app.set_root(VBox(bar, Label("below")))
    app.step()
    return bar, panel, picked


def key(app, k, name=""):
    app.dispatch(KeyEvent(k, Mod.NONE, name))


def test_submenu_marker_is_drawn(app):
    bar, _panel, _ = setup(app)
    bar.open_menu(0)
    app.step()
    rows = app.screen_text()
    line = next(r for r in rows if "Right panel" in r)
    assert "▸" in line and "Local echo" in "\n".join(rows)


def test_keyboard_opens_and_closes_the_submenu(app):
    bar, _panel, picked = setup(app)
    bar.open_menu(0)
    popup = app.popups[-1]
    key(app, Key.DOWN)  # Right panel 로 이동
    key(app, Key.RIGHT)  # 펼치기
    child = app.popups[-1]
    assert isinstance(child, MenuPopup) and child is not popup and child.parent_popup is popup
    app.step()
    assert "HEX view" in "\n".join(app.screen_text())

    key(app, Key.LEFT)  # 한 단계만 접는다
    assert app.popups[-1] is popup and popup.child is None

    key(app, Key.RIGHT)
    key(app, Key.RETURN)  # 하위 첫 항목 실행
    assert picked == ["hex"] and not app.popups  # 실행하면 메뉴 전체가 닫힌다


def test_hotkey_inside_the_submenu(app):
    bar, _panel, picked = setup(app)
    bar.open_menu(0)
    key(app, Key.DOWN)
    key(app, Key.RIGHT)
    app.dispatch(KeyEvent(pygame.K_t, Mod.NONE, "t"))  # Memo 의 key (글자 키는 pygame 상수)
    assert picked == ["memo"] and not app.popups


def test_mouse_hover_opens_the_submenu_and_click_runs_it(app):
    bar, _panel, picked = setup(app)
    bar.open_menu(0)
    popup = app.popups[-1]
    row_y = popup.rect.y + 2  # 두 번째 항목 (Right panel)
    app.dispatch(MouseEvent("move", 0, popup.rect.x + 3, row_y, 0, 0))
    child = app.popups[-1]
    assert child is not popup and child.menu.title == "Right panel"

    app.dispatch(MouseEvent("down", 1, child.rect.x + 3, child.rect.y + 1, 0, 0))
    app.dispatch(MouseEvent("up", 1, child.rect.x + 3, child.rect.y + 1, 0, 0))
    assert picked == ["hex"]


def test_submenu_opens_to_the_left_when_there_is_no_room(app):
    picked = []
    panel = MenuItem("Right panel", submenu=[MenuItem("HEX view", lambda: picked.append("hex"))])
    bar = MenuBar([Menu("A", [MenuItem("x")]), Menu("View", [panel])])
    app.set_root(VBox(bar, Label("below")))
    app.step()
    bar.open_menu(1)
    popup = app.popups[-1]
    popup.select(0)
    child = popup.open_submenu(0)
    app.step()
    assert child is not None and child.rect.right <= app.cols
