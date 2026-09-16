import numpy as np
import pygame
import pytest

from retroui import App, Button, HBox, LivePlot, Spacer, VBox
from retroui.input.events import Key, KeyEvent, Mod, MouseEvent
from retroui.widgets.menu import Menu, MenuBar, MenuItem, MenuPopup

GREEN = (85, 255, 85)


@pytest.fixture
def app():
    try:
        a = App(headless=True, size=(40, 16), theme="dos_blue")
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))
    yield a
    a.close()


def key(k, mod=Mod.NONE, name=""):
    return KeyEvent(k, mod, name)


def mouse(app, kind, cx, cy):
    app.dispatch(MouseEvent(kind, 0 if kind == "move" else 1, cx, cy, 0, 0))


def click(app, cx, cy):
    mouse(app, "down", cx, cy)
    mouse(app, "up", cx, cy)


@pytest.fixture
def ui(app):
    log = []
    bar = MenuBar(
        [
            Menu(
                "한",
                [
                    MenuItem("한글 이란", lambda: log.append("about")),
                    MenuItem("도움말", lambda: log.append("help"), shortcut="F1"),
                    MenuItem.sep(),
                    MenuItem("계산기", enabled=False),
                ],
            ),
            Menu("&Edit", [MenuItem("외곽선", key="O", checked=False), MenuItem("그림자", key="S", checked=True)]),
        ]
    )
    btn = Button("Base", on_click=lambda: log.append("base"))
    app.set_root(VBox(bar, Spacer(size=8, stretch=0), HBox(Spacer(), btn)))
    app.screen_text()
    return app, bar, btn, log


# 메뉴 제목 위치: "한" 은 열 1..4 (글자 2..3), "Edit" 는 열 5..10


def test_f10_opens_first_menu_as_box(ui):
    app, bar, btn, _ = ui
    assert app.focus is btn
    app.dispatch(key(Key.F10))
    lines = app.screen_text()
    assert isinstance(app.focus, MenuPopup)
    assert lines[1].startswith("┌" + "─" * 15 + "┐")
    assert lines[2].startswith("│ 한글 이란")
    assert lines[3].startswith("│ 도움말") and lines[3][:17].rstrip("│ ").endswith("F1")
    assert lines[4].startswith("├" + "─" * 15 + "┤")
    assert app.buf.get(2, 0)[2] == app.theme.palette.sel_bg  # 열린 메뉴 제목 반전


def test_keyboard_activation_closes_and_restores_focus(ui):
    app, bar, btn, log = ui
    app.dispatch(key(Key.F10))
    app.dispatch(key(Key.DOWN))
    app.dispatch(key(Key.RETURN))
    assert log == ["help"]
    assert not app.popups
    assert app.focus is btn
    assert not app.screen_text()[1].startswith("┌")


def test_separator_and_disabled_items_are_skipped(ui):
    app, _, _, _ = ui
    app.dispatch(key(Key.F10))
    popup = app.focus
    app.dispatch(key(Key.DOWN))
    assert popup.selected == 1
    app.dispatch(key(Key.DOWN))
    assert popup.selected == 0  # 구분선, 비활성 항목 건너뛰고 처음으로
    app.dispatch(key(Key.UP))
    assert popup.selected == 1


def test_left_right_switches_menus(ui):
    app, bar, _, _ = ui
    app.dispatch(key(Key.F10))
    app.dispatch(key(Key.RIGHT))
    assert bar.open_index == 1 and app.focus.menu.title == "Edit"
    app.dispatch(key(Key.RIGHT))
    assert bar.open_index == 0
    app.dispatch(key(Key.LEFT))
    assert bar.open_index == 1
    assert len(app.popups) == 1


def test_alt_mnemonic_and_hotkey_toggle_check(ui):
    app, bar, _, _ = ui
    app.dispatch(key(pygame.K_e, Mod.ALT, "e"))
    assert bar.open_index == 1
    app.dispatch(key(pygame.K_o, Mod.NONE, "o"))
    assert bar.menus[1].items[0].checked is True
    assert app.popups  # 체크 항목은 메뉴를 열어 둔다
    assert "√" in app.screen_text()[2]
    app.dispatch(key(Key.ESCAPE, Mod.NONE, "escape"))
    assert not app.popups


def test_escape_closes(ui):
    app, bar, btn, _ = ui
    app.dispatch(key(Key.F10))
    app.dispatch(key(Key.ESCAPE))
    assert not app.popups and bar.open_index is None
    assert app.focus is btn


def test_tab_does_not_leak_while_menu_open(ui):
    app, _, _, _ = ui
    app.dispatch(key(Key.F10))
    popup = app.focus
    app.dispatch(key(Key.TAB))
    assert app.focus is popup


def test_mouse_click_title_then_item(ui):
    app, bar, _, log = ui
    click(app, 2, 0)
    assert bar.open_index == 0
    click(app, 3, 3)
    assert log == ["help"]
    assert not app.popups


def test_click_open_title_again_closes(ui):
    app, bar, _, _ = ui
    click(app, 2, 0)
    click(app, 2, 0)
    assert not app.popups and bar.open_index is None


def test_drag_from_title_to_item_activates(ui):
    app, _, _, log = ui
    mouse(app, "down", 2, 0)
    mouse(app, "move", 3, 2)
    mouse(app, "up", 3, 2)
    assert log == ["about"]


def test_hover_other_title_switches_open_menu(ui):
    app, bar, _, _ = ui
    click(app, 2, 0)
    mouse(app, "move", 7, 0)
    assert bar.open_index == 1


def test_click_outside_closes_and_passes_through(ui):
    app, bar, btn, log = ui
    click(app, 2, 0)
    click(app, btn.rect.x + 1, btn.rect.y)
    assert not app.popups and bar.open_index is None
    assert log == ["base"]


def test_popup_is_not_overdrawn_by_live_plot(app):
    plot = LivePlot("P", y_range=(0.0, 1.0), update_hz=0)
    plot.add_series("a", color="light_green").extend(np.full(300, 0.95))
    bar = MenuBar([Menu("File", [MenuItem("Open recent file"), MenuItem("Save"), MenuItem("Quit")])])
    app.set_root(VBox(bar, plot))
    app.step()
    cw, ch = app.fonts.cw, app.fonts.ch

    def green_in(r):
        return any(
            tuple(app.surface.get_at((x, y))[:3]) == GREEN
            for y in range(r.y * ch, r.bottom * ch)
            for x in range(r.x * cw, r.right * cw)
        )

    app.dispatch(key(Key.F10))
    app.step()
    overlap = app.popups[-1].rect.intersect(plot.pixel_rect())
    assert not overlap.empty
    assert not green_in(overlap)

    app.dispatch(key(Key.ESCAPE))
    app.step()
    assert green_in(overlap)
