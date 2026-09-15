import time

import pygame
import pytest
from retroui import Dialog
from retroui.input.events import Key, KeyEvent, Mod, TextEvent

from baram_term import i18n
from baram_term.app import BaramTerm
from baram_term.logo import LOGO
from baram_term.serial_port import PortSettings


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


def screen(term):
    return "\n".join(term.app.screen_text())


def pump(term, cond, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        term.app.step()
        if cond():
            return True
        time.sleep(0.01)
    return False


def key(k, mod=Mod.NONE, name=""):
    return KeyEvent(k, mod, name)


def test_banner_status_and_demo_boot(bt):
    text = screen(bt)
    assert LOGO[0] in text and "firmware CLI serial terminal" in text
    bt.connect()
    assert pump(bt, lambda: "cli#" in screen(bt))
    text = screen(bt)
    assert "[OK] uartInit()" in text
    assert "connected to demo:// (115200 8N1)" in text
    status = bt.app.screen_text()[-1]
    assert "●" in status and "demo://" in status and "115200 8N1" in status


def test_typed_command_runs_on_device(bt):
    bt.connect()
    assert pump(bt, lambda: "cli#" in screen(bt))
    for ch in "help":
        bt.app.dispatch(TextEvent(ch))
    bt.app.dispatch(key(Key.RETURN, name="return"))
    assert pump(bt, lambda: "cmd list" in screen(bt))


def test_ctrl_a_prefix_commands(bt):
    bt.app.dispatch(key(pygame.K_a, Mod.CTRL, "a"))
    assert bt._prefix and "Ctrl-A" in bt.app.screen_text()[-1]
    bt.app.dispatch(key(pygame.K_e, Mod.NONE, "e"))
    assert bt.local_echo and bt.item_echo.checked and not bt._prefix

    bt.app.dispatch(key(pygame.K_a, Mod.CTRL, "a"))
    bt.app.dispatch(key(pygame.K_c, Mod.NONE, "c"))
    assert LOGO[0] not in screen(bt)

    bt.app.dispatch(key(pygame.K_a, Mod.CTRL, "a"))
    bt.app.dispatch(key(pygame.K_o, Mod.NONE, "o"))
    assert isinstance(bt.app.popups[-1], Dialog)
    bt.app.dispatch(key(Key.ESCAPE, name="escape"))
    assert not bt.app.popups


def test_modifier_key_does_not_consume_prefix(bt):
    bt.app.dispatch(key(pygame.K_a, Mod.CTRL, "a"))
    bt.app.dispatch(key(pygame.K_LSHIFT, Mod.SHIFT, "left shift"))
    assert bt._prefix


def test_typing_while_disconnected_shows_notice(bt):
    bt.app.dispatch(TextEvent("x"))
    assert "not connected" in screen(bt)


def test_device_unplug_is_reported(bt):
    bt._apply_reconnect(False)  # 재연결은 test_persistence.py 에서 따로 확인
    bt.connect()
    assert pump(bt, lambda: "cli#" in screen(bt))
    bt.port.device.close()  # 장치 제거 흉내
    assert pump(bt, lambda: "port error" in screen(bt))
    assert not bt.port.is_open
    assert "○" in bt.app.screen_text()[-1]


def test_open_failure_is_reported():
    i18n.set_language("en")

    def failing_opener(settings):
        raise OSError("no such port")

    try:
        term = BaramTerm(PortSettings(port="/dev/nope"), headless=True, size=(80, 20), opener=failing_opener)
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))
    try:
        term.connect()
        assert "failed to open /dev/nope: no such port" in screen(term)
    finally:
        term.app.close()
