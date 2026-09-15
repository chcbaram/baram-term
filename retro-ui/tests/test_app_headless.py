import threading
import time

import pygame
import pytest

from retroui import App, Button, CheckBox, GroupBox, HBox, Label, Signal, Spacer, VBox
from retroui.input.events import Key, KeyEvent, Mod, MouseEvent
from retroui.render.cellbuffer import Attr


@pytest.fixture
def app():
    try:
        a = App(headless=True, size=(30, 8), theme="dos_blue")
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))
    yield a
    a.close()


def key(k, mod=Mod.NONE, name=""):
    return KeyEvent(k, mod, name)


def click(app, w, dx=0):
    app.dispatch(MouseEvent("down", 1, w.rect.x + dx, w.rect.y, 0, 0))
    app.dispatch(MouseEvent("up", 1, w.rect.x + dx, w.rect.y, 0, 0))


def test_hbox_spacer_pushes_label_to_the_right(app):
    app.set_root(VBox(HBox(Label("ab"), Spacer(), Label("cd"))))
    lines = app.screen_text()
    assert lines[0] == "ab" + " " * 26 + "cd"
    assert lines[1].strip() == ""


def test_groupbox_title_and_focus_border(app):
    app.set_root(VBox(GroupBox("제목", Label("안녕")), GroupBox("버튼", Button("OK"))))
    lines = app.screen_text()
    assert lines[0].startswith("┌┤ 제목 ├")
    assert lines[1].startswith("│안녕")
    # 포커스를 가진 버튼이 들어 있는 그룹은 이중선 테두리
    focus_row = next(i for i, line in enumerate(lines) if "버튼" in line)
    assert lines[focus_row].startswith("╔╣ 버튼 ╠")


def test_tab_moves_focus_and_space_activates(app):
    clicks = []
    b1 = Button("A", on_click=lambda: clicks.append("A"))
    b2 = Button("B", on_click=lambda: clicks.append("B"))
    cb = CheckBox("chk")
    app.set_root(VBox(b1, b2, cb))
    app.step()
    assert app.focus is b1

    app.dispatch(key(Key.TAB))
    assert app.focus is b2
    app.dispatch(key(Key.SPACE))
    assert clicks == ["B"]

    app.dispatch(key(Key.TAB))
    app.dispatch(key(Key.SPACE))
    assert cb.checked
    assert app.screen_text()[2].startswith("[x] chk")

    app.dispatch(key(Key.TAB))
    assert app.focus is b1  # 순환
    app.dispatch(key(Key.TAB, Mod.SHIFT))
    assert app.focus is cb


def test_mouse_click_and_drag_out_cancels(app):
    clicks = []
    b = Button("Go", on_click=lambda: clicks.append(1))
    app.set_root(VBox(Label("x"), b))
    app.step()

    click(app, b, dx=2)
    assert clicks == [1]
    assert app.focus is b

    app.dispatch(MouseEvent("down", 1, b.rect.x, b.rect.y, 0, 0))
    app.dispatch(MouseEvent("move", 0, 29, 7, 0, 0))
    app.dispatch(MouseEvent("up", 1, 29, 7, 0, 0))
    assert clicks == [1]
    assert not b.pressed


def test_disabled_button_ignores_input(app):
    clicks = []
    b = Button("Go", on_click=lambda: clicks.append(1), enabled=False)
    app.set_root(VBox(b))
    app.step()
    assert app.focus is None
    click(app, b)
    assert clicks == []


def test_alt_mnemonic_clicks_and_is_underlined(app):
    clicks = []
    b = Button("&Start", on_click=lambda: clicks.append(1))
    app.set_root(VBox(Label("x"), b))
    app.screen_text()
    app.dispatch(key(pygame.K_s, Mod.ALT, "s"))
    assert clicks == [1]
    underlined = [x for x in range(b.rect.x, b.rect.right) if app.buf.get(x, b.rect.y)[3] & Attr.UNDERLINE]
    assert len(underlined) == 1
    assert app.buf.get(underlined[0], b.rect.y)[0] == "S"


def test_shortcut(app):
    hits = []
    app.add_shortcut("Ctrl+Q", lambda: hits.append(1))
    app.set_root(VBox(Label("x")))
    app.dispatch(key(pygame.K_q, Mod.CTRL, "q"))
    app.dispatch(key(pygame.K_q, Mod.CTRL | Mod.SHIFT, "q"))  # 수정자가 다르면 불일치
    assert hits == [1]


def test_signal_from_worker_thread_updates_label(app):
    label = Label("waiting")
    app.set_root(VBox(label))
    sig = Signal()
    sig.connect(label.set_text)
    th = threading.Thread(target=sig.emit, args=("- DONE -",))
    th.start()
    th.join()
    assert label.text == "waiting"  # 아직 메인 스레드에서 실행 전
    app.step()
    assert app.screen_text()[0].startswith("- DONE -")


def test_timer_runs_in_step(app):
    fired = []
    app.set_timeout(1, lambda: fired.append(1))
    time.sleep(0.01)
    app.step()
    assert fired == [1]


def test_label_update_only_redraws_changed_cells(app):
    label = Label("value: 10")
    app.set_root(VBox(label, Label("static")))
    app.step()
    label.set_text("value: 11")
    rects = app._paint()
    assert len(rects) == 1
    assert rects[0].width == app.fonts.cw  # '0' -> '1' 한 칸만


def test_hover_highlights_button_and_checkbox(app):
    b = Button("Go")
    cb = CheckBox("chk")
    app.set_root(VBox(Label("x"), b, cb))
    app.screen_text()
    button_bg = app.buf.get(b.rect.x + 1, b.rect.y)[2]
    check_bg = app.buf.get(cb.rect.x, cb.rect.y)[2]

    app.dispatch(MouseEvent("move", 0, b.rect.x + 1, b.rect.y, 0, 0))
    app.screen_text()
    assert b.hovered
    assert app.buf.get(b.rect.x + 1, b.rect.y)[2] != button_bg

    app.dispatch(MouseEvent("move", 0, cb.rect.x, cb.rect.y, 0, 0))
    app.screen_text()
    assert not b.hovered and cb.hovered
    assert app.buf.get(b.rect.x + 1, b.rect.y)[2] == button_bg
    assert app.buf.get(cb.rect.x, cb.rect.y)[2] != check_bg
