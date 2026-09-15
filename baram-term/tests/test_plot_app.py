import time

import pygame
import pytest
from retroui.input.events import Key, KeyEvent, Mod, TextEvent

from baram_term import i18n
from baram_term import settings as store
from baram_term.app import BaramTerm
from baram_term.serial_port import PortSettings
from baram_term.settings import Settings


def make(**kw):
    i18n.set_language("en")
    try:
        return BaramTerm(PortSettings(port="demo://"), headless=True, size=(80, 36), **kw)
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))


@pytest.fixture
def bt():
    term = make()
    yield term
    term.port.close()
    term.app.close()


def pump(term, cond, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        term.app.step()
        if cond():
            return True
        time.sleep(0.01)
    return False


def run_command(term, command):
    for ch in command:
        term.app.dispatch(TextEvent(ch))
    term.app.dispatch(KeyEvent(Key.RETURN, Mod.NONE, ""))


def counts(term):
    return {name: len(s.buffer) for name, s in term._plot_series.items()}


def test_panel_toggle_with_ctrl_a_g_and_persist(tmp_path):
    path = tmp_path / "settings.json"
    term = make(config=Settings(), config_path=path)
    try:
        assert not term.plot_frame.visible and not term.item_plot.checked
        term.app.dispatch(KeyEvent(pygame.K_a, Mod.CTRL, "a"))
        term.app.dispatch(KeyEvent(pygame.K_g, Mod.NONE, "g"))
        assert term.plot_frame.visible and term.item_plot.checked
        term.app.step()
        assert term.plot.rect.h > 0 and term.frame.rect.h > term.plot_frame.rect.h
    finally:
        term.port.close()
        term.app.close()
    saved = store.load(path)[0]
    assert saved.plot is True
    again = make(config=saved, config_path=path)
    try:
        assert again.plot_frame.visible and again.item_plot.checked
    finally:
        again.port.close()
        again.app.close()


def test_teleplot_stream_from_demo_device(bt):
    bt._apply_plot(True)
    bt.connect()
    assert pump(bt, lambda: bt.terminal.screen.line_text(bt.terminal.screen.cy) == "cli#")
    run_command(bt, "plot")
    assert pump(bt, lambda: all(counts(bt).get(n, 0) >= 3 for n in ("ax", "ay", "az", "temp")))
    assert [s.name for s in bt.plot.series] == ["ax", "ay", "az", "temp"]
    run_command(bt, "plot off")
    bt.app.step()


def test_arduino_stream_from_demo_device(bt):
    bt._apply_plot(True)
    bt.connect()
    assert pump(bt, lambda: bt.terminal.screen.line_text(bt.terminal.screen.cy) == "cli#")
    run_command(bt, "plot arduino")
    assert pump(bt, lambda: all(counts(bt).get(n, 0) >= 3 for n in ("ax", "ay", "az", "temp")))


def test_split_chunks_and_log_lines(bt):
    bt._apply_plot(True)
    bt._feed_plot(">a")
    bt._feed_plot("x:1\r\n[OK] sensor temp=42 rpm=1\r\n>ax:2\r\n10 20\r\n")
    assert counts(bt) == {"ax": 2, "value 1": 1, "value 2": 1}
    assert list(bt._plot_series["ax"].buffer.snapshot()[1]) == [1.0, 2.0]


def test_hidden_panel_ignores_data_and_series_are_capped(bt):
    bt.port.device = None
    bt.terminal.feed("")
    bt._on_rx()  # 포트가 없어도 문제없이
    bt._feed_plot(" ".join(str(i) for i in range(20)) + "\r\n")
    assert len(bt._plot_series) == bt.PLOT_MAX_SERIES


def test_clear_removes_series_and_pause_toggles(bt):
    bt._apply_plot(True)
    bt._feed_plot(">ax:1\r\n>ay:2\r\n")
    bt.toggle_plot_pause()
    assert bt.plot.paused
    bt.toggle_plot_pause()
    bt.clear_plot()
    assert bt.plot.series == [] and bt._plot_series == {}
    bt._feed_plot(">gz:3\r\n")
    assert [s.name for s in bt.plot.series] == ["gz"]


def test_plot_does_not_take_keyboard_focus(bt):
    from retroui.input.events import MouseEvent

    bt._apply_plot(True)
    bt.app.step()
    r = bt.plot.rect
    bt.app.dispatch(MouseEvent("down", 1, r.x + r.w // 2, r.y + r.h // 2, 0, 0))
    bt.app.dispatch(MouseEvent("up", 1, r.x + r.w // 2, r.y + r.h // 2, 0, 0))
    assert bt.app.focus is bt.terminal


def test_x_axis_is_arrival_time(bt):
    clock = [100.0]
    bt.plot_clock = lambda: clock[0]
    bt.clear_plot()  # 0초부터 다시
    bt._feed_plot(">ax:1\r\n")
    clock[0] = 102.5
    bt._feed_plot(">ax:2\r\n")
    xs, ys, _ = bt._plot_series["ax"].buffer.snapshot()
    assert list(xs) == [0.0, 2.5] and list(ys) == [1.0, 2.0]
    assert bt.plot.window == 10.0


def test_plot_window_dialog_sets_validates_and_persists(tmp_path):
    path = tmp_path / "settings.json"
    term = make(config=Settings(), config_path=path)
    try:
        d = term.ask_plot_window()
        assert d.combo.text == "10" and term.app.focus is d.combo
        d.combo.set_text("30")
        d.finish(0)
        assert term.plot.window == 30.0

        d = term.ask_plot_window()
        d.combo.set_text("")
        d.finish(0)
        assert term.plot.window == 30.0 and "invalid time window" in "\n".join(term.app.screen_text())

        d = term.ask_plot_window()
        for ch in "2.5x":
            term.app.dispatch(TextEvent(ch))  # 전체 선택된 30 을 바꿔 쓴다, x 는 무시
        term.app.dispatch(KeyEvent(Key.RETURN, Mod.NONE, ""))
        assert term.plot.window == 2.5
    finally:
        term.port.close()
        term.app.close()
    saved = store.load(path)[0]
    assert saved.plot_window == 2.5
    again = make(config=saved, config_path=path)
    try:
        assert again.plot.window == 2.5
    finally:
        again.port.close()
        again.app.close()


def click(term, widget, dx=1):
    from retroui.input.events import MouseEvent

    term.app.ensure_layout()
    x, y = widget.rect.x + dx, widget.rect.y
    term.app.dispatch(MouseEvent("down", 1, x, y, 0, 0))
    term.app.dispatch(MouseEvent("up", 1, x, y, 0, 0))


def test_top_row_has_legend_and_run_button(bt):
    bt._apply_plot(True)
    bt._feed_plot(">ax:1\r\n>ay:2\r\n")
    bt.app.step()
    legend, button = bt.plot_legend, bt.plot_run_button
    assert legend.rect.y == button.rect.y and button.rect.right > legend.rect.x
    row = bt.app.screen_text()[legend.rect.y]
    assert "■ ax" in row and "■ ay" in row and "STOP" in row
    assert bt.plot.pixel_rect().y == legend.rect.y + 1  # 그래프는 바로 다음 줄부터


def test_run_button_toggles_and_keeps_terminal_focus(bt):
    from retroui.input.events import MouseEvent

    bt._apply_plot(True)
    bt.app.step()
    width = bt.plot_run_button.rect.w
    b = bt.plot_run_button
    bt.app.dispatch(MouseEvent("down", 1, b.rect.x + 1, b.rect.y, 0, 0))
    bt.app.step()
    assert bt.app.focus is bt.terminal and "►" not in bt.app.screen_text()[b.rect.y]  # 누르고 있는 동안에도
    bt.app.dispatch(MouseEvent("up", 1, b.rect.x + 1, b.rect.y, 0, 0))
    assert bt.plot.paused
    click(bt, bt.plot_run_button)
    assert not bt.plot.paused
    click(bt, bt.plot_run_button)
    assert bt.plot.paused and bt.plot_run_button.text == "START" and bt.plot_run_button.fill_color == "ok"
    assert bt.app.focus is bt.terminal
    bt.app.step()
    assert bt.plot_run_button.rect.w == width
    click(bt, bt.plot_run_button)
    assert not bt.plot.paused and bt.plot_run_button.text == "STOP"


def test_legend_click_hides_series(bt):
    bt._apply_plot(True)
    bt._feed_plot(">ax:1\r\n>ay:2\r\n")
    bt.app.step()
    click(bt, bt.plot_legend, dx=1)
    assert bt._plot_series["ax"].visible is False and bt._plot_series["ay"].visible is True
    assert bt.app.focus is bt.terminal


def test_window_combo_sits_bottom_right_and_applies(bt):
    bt._apply_plot(True)
    bt.app.ensure_layout()
    combo, frame = bt.plot_window_combo, bt.plot_frame
    assert combo.text == "10"
    assert combo.rect.y > bt.plot.rect.bottom - 1 and combo.rect.y == frame.rect.bottom - 2  # 테두리 바로 위 줄
    assert frame.rect.right - 1 - combo.rect.right <= len("seconds") + 2  # 오른쪽 끝

    click(bt, combo, dx=combo.rect.w - 2)  # ▼
    popup = bt.app.popups[-1]
    popup.choose(popup.items.index("60"))
    assert bt.plot.window == 60.0 and bt.app.focus is bt.terminal

    bt.app.set_focus(combo)
    combo.select_all()
    for ch in "2.5":
        bt.app.dispatch(TextEvent(ch))
    assert bt.plot.window == 2.5 and combo.text == "2.5"
    bt.app.dispatch(KeyEvent(Key.RETURN, Mod.NONE, ""))
    assert bt.app.focus is bt.terminal

    bt.app.set_focus(combo)
    combo.set_text("")
    bt.app.dispatch(KeyEvent(Key.RETURN, Mod.NONE, ""))
    assert combo.text == "2.5" and "invalid time window" in "\n".join(bt.app.screen_text())

    d = bt.ask_plot_window()  # 메뉴 대화상자로 바꾸면 아래 칸도 따라간다
    d.combo.set_text("30")
    d.finish(0)
    assert combo.text == "30" and bt.plot.window == 30.0


def test_drag_boundary_resizes_plot_and_persists(tmp_path):
    from retroui.input.events import MouseEvent

    path = tmp_path / "settings.json"
    term = make(config=Settings(), config_path=path)
    try:
        term._apply_plot(True)
        term.app.step()
        frame, plot_frame, split = term.frame, term.plot_frame, term.split
        total = frame.rect.h + plot_frame.rect.h
        assert frame.rect.h == round(total * 2 / 3)
        y = split.split_y - 1  # 터미널 아래 테두리
        assert term.app.cursor_name(frame, 5, y) == "resize_ns"

        before = plot_frame.rect.h
        term.app.dispatch(MouseEvent("down", 1, 5, y, 0, 0))
        term.app.dispatch(MouseEvent("move", 0, 5, y - 6, 0, 0))
        term.app.dispatch(MouseEvent("up", 1, 5, y - 6, 0, 0))
        term.app.step()
        assert plot_frame.rect.h == before + 6 and term.app.focus is term.terminal

        term.app.dispatch(MouseEvent("down", 1, 5, split.split_y, 0, 0))
        term.app.dispatch(MouseEvent("move", 0, 5, 0, 0, 0))
        term.app.dispatch(MouseEvent("up", 1, 5, 0, 0, 0))
        term.app.step()
        assert frame.rect.h == 5  # 터미널 최소 높이
        ratio = split.ratio
    finally:
        term.port.close()
        term.app.close()

    saved = store.load(path)[0]
    assert saved.plot_split == round(ratio, 4)
    again = make(config=saved, config_path=path)
    try:
        again.app.step()
        assert again.frame.rect.h == 5
        again._apply_plot(False)
        again.app.step()
        assert again.frame.rect.h == total  # 그래프를 끄면 터미널이 전부
    finally:
        again.port.close()
        again.app.close()
