import time
from types import SimpleNamespace

import pygame
import pytest
from retroui import TerminalScreen
from retroui.input.events import Key, KeyEvent, Mod, TextEvent

from baram_term import i18n
from baram_term.app import BaramTerm
from baram_term.completion import at_prompt
from baram_term.outgoing import outgoing_bytes
from baram_term.serial_port import PortSettings


def out(data, at=True, guard=True):
    return outgoing_bytes(data, at_prompt=at, guard=guard)


def test_prompt_filters_tab_and_control_keys():
    assert out(b"\t") == b""
    assert out(b"\x03") == b""  # Ctrl+C
    assert out(b"\x01") == b""


def test_line_editing_keys_and_text_pass():
    for data in (b"\r", b"\x08", b"\x7f", b"\x1b[A", b"\x1b[1~", b"h", "가".encode()):
        assert out(data) == data


def test_pasted_text_tabs_become_spaces():
    assert out(b"md\t0x08\x00\r") == b"md 0x08\r"


def test_not_at_prompt_or_guard_off_sends_as_is():
    assert out(b"\x03", at=False) == b"\x03"  # 명령 실행 중 Ctrl+C
    assert out(b"\t", guard=False) == b"\t"


def fake_terminal(text):
    screen = TerminalScreen(80, 10)
    screen.feed(text)
    return SimpleNamespace(screen=screen)


def test_at_prompt_includes_argument_typing():
    assert at_prompt(fake_terminal("\n\rcli# md 0x"))
    assert not at_prompt(fake_terminal("\n\rcli# help\r\nrunning..."))


@pytest.fixture
def bt():
    i18n.set_language("en")
    try:
        term = BaramTerm(PortSettings(port="demo://"), headless=True, size=(80, 30))
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))
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


def ready(term):
    term.connect()
    assert pump(term, lambda: at_prompt(term.terminal))
    term._apply_complete(False)  # Tab 이 자동완성에 쓰이지 않고 보내기 경로로 가게


def test_tab_is_not_inserted_into_firmware_line(bt):
    ready(bt)
    for ch in "he":
        bt.app.dispatch(TextEvent(ch))
    assert pump(bt, lambda: bt.port.device.line == "he")
    bt.app.dispatch(KeyEvent(Key.TAB, Mod.NONE, "tab"))
    bt.app.dispatch(KeyEvent(pygame.K_c, Mod.CTRL, "c"))
    bt.app.dispatch(TextEvent("l"))
    assert pump(bt, lambda: bt.port.device.line == "hel")
    screen = bt.terminal.screen
    assert screen.line_text(screen.cy) == "cli# hel" and screen.cx == len("cli# hel")


def test_guard_off_reproduces_firmware_tab_problem(bt):
    ready(bt)
    bt._apply_guard(False)
    bt.app.dispatch(TextEvent("h"))
    bt.app.dispatch(KeyEvent(Key.TAB, Mod.NONE, "tab"))
    assert pump(bt, lambda: bt.port.device.line == "h\t")


def test_ctrl_a_ctrl_a_still_sends_literal(bt):
    ready(bt)
    before = bt.port.tx_bytes
    bt.app.dispatch(KeyEvent(pygame.K_a, Mod.CTRL, "a"))
    bt.app.dispatch(KeyEvent(pygame.K_a, Mod.CTRL, "a"))
    assert pump(bt, lambda: bt.port.device.line == "\x01")
    # 송신 스레드는 장치에 쓴 뒤에 카운터를 올리므로 기다렸다가 확인한다
    assert pump(bt, lambda: bt.port.tx_bytes == before + 1)
