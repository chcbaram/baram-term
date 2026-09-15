import time

import pygame
import pytest
from retroui import Dialog
from retroui.input.events import Key, KeyEvent, Mod, TextEvent

from baram_term import i18n
from baram_term.app import BaramTerm
from baram_term.serial_port import PortSettings


@pytest.fixture
def bt():
    i18n.set_language("en")
    try:
        term = BaramTerm(PortSettings(port="demo://"), headless=True, size=(80, 30))
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))
    yield term
    term.stop_log(notify=False)
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


def screen(term):
    return "\n".join(term.app.screen_text())


def status(term):
    return term.app.screen_text()[-1]


def ctrl_a(term, name):
    term.app.dispatch(KeyEvent(pygame.K_a, Mod.CTRL, "a"))
    term.app.dispatch(KeyEvent(getattr(pygame, f"K_{name}"), Mod.NONE, name))


def test_session_is_logged_as_clean_lines(bt, tmp_path):
    path = tmp_path / "session.log"
    assert bt.start_log(str(path), timestamps=False)  # 연결 전에 시작: 부팅 출력과 프롬프트까지 남긴다
    assert "LOG" in status(bt)
    bt.connect()
    assert pump(bt, lambda: "cli#" in screen(bt))

    for ch in "helx":
        bt.app.dispatch(TextEvent(ch))
    bt.app.dispatch(KeyEvent(Key.BACKSPACE, Mod.NONE, ""))
    bt.app.dispatch(TextEvent("p"))
    bt.app.dispatch(KeyEvent(Key.RETURN, Mod.NONE, ""))
    assert pump(bt, lambda: "cmd list" in screen(bt))
    bt.disconnect()
    bt.stop_log()

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines[0].startswith("--- baram-term") and "demo:// 115200 8N1" in lines[0]
    assert "cli# help" in lines  # 백스페이스로 고친 결과만 남는다
    assert any("cmd list" in line for line in lines)
    assert "\x1b" not in text and "\b" not in text and "\r" not in text
    assert any(line.startswith("--- ") and "disconnected" in line for line in lines)
    assert "LOG" not in status(bt) and "log saved" in screen(bt)


def test_ctrl_a_l_opens_dialog_then_stops(bt, tmp_path):
    ctrl_a(bt, "l")
    dialog = bt.app.popups[-1]
    assert isinstance(dialog, Dialog)
    assert dialog.path_edit.text.endswith("_demo.log") and dialog.timestamps_box.checked

    path = tmp_path / "logs" / "demo.log"
    dialog.path_edit.set_text(str(path))
    dialog.timestamps_box.set_checked(False)
    bt.app.set_focus(dialog.path_edit)
    bt.app.dispatch(KeyEvent(Key.RETURN, Mod.NONE, ""))
    assert not bt.app.popups and bt.log is not None and path.exists()
    assert bt.config.log_dir == str(path.parent) and bt.config.log_timestamps is False

    ctrl_a(bt, "l")  # 기록 중이면 바로 멈춘다
    assert bt.log is None and not bt.app.popups


def test_timestamps_prefix_each_line(bt, tmp_path):
    path = tmp_path / "ts.log"
    assert bt.start_log(str(path), timestamps=True)
    bt.notice("hello")
    bt.stop_log()
    last = path.read_text(encoding="utf-8").splitlines()[-1]
    assert last[0] == "[" and last[13:] == "] --- hello"


def test_open_failure_is_reported(bt, tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    assert not bt.start_log(str(blocker / "x.log"), timestamps=False)
    assert bt.log is None and "could not open log file" in screen(bt)


def test_write_failure_stops_logging_but_terminal_keeps_running(bt, tmp_path):
    bt.connect()
    assert pump(bt, lambda: "cli#" in screen(bt))
    assert bt.start_log(str(tmp_path / "gone.log"), timestamps=False)
    bt.log._fp.close()  # 저장장치가 빠진 것처럼
    bt.app.dispatch(KeyEvent(Key.RETURN, Mod.NONE, ""))  # 줄이 끝나야 파일에 쓴다
    assert pump(bt, lambda: bt.log is None)
    assert "logging stopped" in screen(bt) and "LOG" not in status(bt)
    assert bt.port.is_open
