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
    assert counts(bt) == {"ax": 2}  # ">" 형식으로 시작했으니 Arduino 형식 "10 20" 은 받지 않는다
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

    bt.set_plot_window(30)  # 프로그램에서 바꿔도 아래 칸이 따라간다
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


def test_plot_lines_hidden_from_terminal_while_prompt_stays(tmp_path):
    path = tmp_path / "settings.json"
    term = make(config=Settings(), config_path=path)
    try:
        assert term.plot_hide_lines is False and not term.item_plot_hide.checked  # 기본은 끔
        term._apply_plot(True)
        term._apply_plot_hide(True)
        term.connect()
        assert pump(term, lambda: term.terminal.screen.line_text(term.terminal.screen.cy) == "cli#")
        run_command(term, "plot")
        assert pump(term, lambda: all(counts(term).get(n, 0) >= 5 for n in ("ax", "ay", "az", "temp")))
        term._update_status()
        term.app.step()
        text = "\n".join(term.app.screen_text())
        assert ">ax:" not in text and "PLOT" in term.app.screen_text()[-1]
        scr = term.terminal.screen
        assert scr.line_text(scr.cy) == "cli#"  # 프롬프트가 두 번 찍히지 않는다

        for ch in "st":
            term.app.dispatch(TextEvent(ch))
        assert pump(term, lambda: scr.line_text(scr.cy) == "cli# st")  # 값이 계속 와도 입력 중인 줄 유지

        term._apply_plot_hide(False)
        assert pump(term, lambda: ">ax:" in "\n".join(term.app.screen_text()))
        assert "PLOT" not in term.app.screen_text()[-1] or not term.plot_hide_lines
        run_command(term, "plot off")
    finally:
        term.port.close()
        term.app.close()
    assert store.load(path)[0].plot_hide_lines is False


def test_clear_button_clears_and_keeps_focus(bt):
    bt._apply_plot(True)
    bt._feed_plot(">ax:1\r\n")
    bt.app.step()
    assert bt.plot_clear_button.rect.right <= bt.plot_run_button.rect.x  # STOP 왼쪽
    click(bt, bt.plot_clear_button)
    assert bt.plot.series == [] and bt.app.focus is bt.terminal


def test_teleplot_format_is_locked_against_stray_lines(bt):
    bt._apply_plot(True)
    bt._feed_plot(">ax:1\r\np:34\r\n>ay:2\r\n")  # 잘린 ">temp:34" 가 "p:34" 로 온 경우
    assert sorted(bt._plot_series) == ["ax", "ay"]
    bt.clear_plot()
    bt._feed_plot("p:34\r\n")  # 지우면 새 형식으로 다시 시작
    assert sorted(bt._plot_series) == ["p"]


def test_a_teleplot_line_takes_the_format_back_from_a_log_line(bt):
    """평범한 로그가 Arduino 형식으로 읽혀 형식을 채 가도, 진짜 그래프 줄이 되찾는다.

    `sensor` 의 `temp=42.0 rpm=1200`, `status` 의 `History : 3` 이 그랬다.
    그 뒤로 진짜 `>ax:-15` 가 전부 버려져 그래프가 비어 있었다.
    """
    bt._apply_plot(True)
    bt._feed_plot("temp=42.0 rpm=1200\r\n")
    assert bt._plot_format == "arduino" and sorted(bt._plot_series) == ["rpm", "temp"]
    bt._feed_plot(">ax:-15\r\n>ay:7\r\n")
    assert bt._plot_format == "tele"
    assert sorted(bt._plot_series) == ["ax", "ay"]  # 잘못 잡힌 시리즈는 버린다


def test_history_line_alone_does_not_block_the_plot(bt):
    bt._apply_plot(True)
    bt._feed_plot("History : 3\r\n>ax:1\r\n")
    assert sorted(bt._plot_series) == ["ax"]


def test_an_arduino_line_never_takes_over_teleplot(bt):
    """반대 방향은 막는다: `>` 로 시작하는 줄은 우연히 나오지 않지만 Arduino 형식은 흔하다."""
    bt._apply_plot(True)
    bt._feed_plot(">ax:1\r\n")
    bt._feed_plot("temp=42.0 rpm=1200\r\n")
    assert bt._plot_format == "tele" and sorted(bt._plot_series) == ["ax"]


def test_typed_echo_is_not_delayed_while_hiding_plot_lines(bt):
    bt._apply_plot(True)
    bt._apply_plot_hide(True)
    bt.connect()
    scr = bt.terminal.screen
    assert pump(bt, lambda: scr.line_text(scr.cy) == "cli#")
    run_command(bt, "plot")
    assert pump(bt, lambda: len(counts(bt)) == 4)
    bt.app.dispatch(TextEvent("s"))
    # 붙잡는 시간(0.2초)보다 훨씬 빨리 보여야 한다
    assert pump(bt, lambda: scr.line_text(scr.cy) == "cli# s", timeout=0.1)
    run_command(bt, "plot off")


def test_plot_window_is_saved_and_restored(tmp_path):
    path = tmp_path / "settings.json"
    term = make(config=Settings(), config_path=path)
    try:
        assert term.plot.window == 10.0
        term.set_plot_window(2.5)
    finally:
        term.port.close()
        term.app.close()
    saved = store.load(path)[0]
    assert saved.plot_window == 2.5
    again = make(config=saved, config_path=path)
    try:
        assert again.plot.window == 2.5 and again.plot_window_combo.text == "2.5"
    finally:
        again.port.close()
        again.app.close()
