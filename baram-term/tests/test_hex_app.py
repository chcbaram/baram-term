import time

import pygame
import pytest
from retroui.input.events import Key, KeyEvent, Mod, MouseEvent, TextEvent

from baram_term import i18n
from baram_term import settings as store
from baram_term.app import BaramTerm
from baram_term.serial_port import PortSettings
from baram_term.settings import Settings


def make(**kw):
    i18n.set_language("en")
    try:
        return BaramTerm(PortSettings(port="demo://"), headless=True, size=(110, 36), **kw)
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


def click(term, widget, dx=1):
    term.app.ensure_layout()
    x, y = widget.rect.x + dx, widget.rect.y
    term.app.dispatch(MouseEvent("down", 1, x, y, 0, 0))
    term.app.dispatch(MouseEvent("up", 1, x, y, 0, 0))


def directions(term):
    return {row[1] for row in term.hex_view.rows}


def test_ctrl_a_h_toggles_panel_and_persists(tmp_path):
    path = tmp_path / "settings.json"
    term = make(config=Settings(), config_path=path)
    try:
        assert not term.hex_frame.visible and not term.item_hex.checked
        term.app.dispatch(KeyEvent(pygame.K_a, Mod.CTRL, "a"))
        term.app.dispatch(KeyEvent(pygame.K_h, Mod.NONE, "h"))
        term.app.step()
        assert term.hex_frame.visible and term.item_hex.checked
        term._update_status()
        term.app.step()
        assert "HEX" in term.app.screen_text()[-1]
        # 터미널 오른쪽에 붙고, 세로 자리는 터미널과 같다 (그래프 패널은 그 아래)
        assert term.frame.rect.right == term.hex_frame.rect.x
        assert (term.hex_frame.rect.y, term.hex_frame.rect.h) == (term.frame.rect.y, term.frame.rect.h)
    finally:
        term.port.close()
        term.app.close()
    assert store.load(path)[0].hex is True


def test_shows_received_and_sent_bytes(bt):
    bt._apply_hex(True)
    bt.connect()
    assert pump(bt, lambda: bt.terminal.screen.line_text(bt.terminal.screen.cy) == "cli#")
    assert directions(bt) == {"rx"}
    for ch in "info":
        bt.app.dispatch(TextEvent(ch))
    bt.app.dispatch(KeyEvent(Key.RETURN, Mod.NONE, ""))
    assert pump(bt, lambda: "tx" in directions(bt))
    bt.app.step()
    text = "\n".join(bt.app.screen_text())
    assert "TX 69 6E 66 6F" in text or "TX 69" in text  # info
    assert "RX" in text and bt.hex_view.next_offset > 0


def test_toolbar_stop_and_clear_keep_terminal_focus(bt):
    bt._apply_hex(True)
    bt.hex_view.append(b"hello", "rx")
    bt.app.step()
    click(bt, bt.hex_run_button)
    assert bt.hex_view.paused and bt.hex_run_button.text == "START"
    assert bt.app.focus is bt.terminal
    click(bt, bt.hex_run_button)
    assert not bt.hex_view.paused and bt.hex_run_button.text == "STOP"
    click(bt, bt.hex_clear_button)
    assert bt.hex_view.rows == [] and bt.app.focus is bt.terminal


def test_hidden_panel_collects_nothing(bt):
    bt.connect()
    assert pump(bt, lambda: bt.terminal.screen.line_text(bt.terminal.screen.cy) == "cli#")
    assert bt.hex_view.rows == []
    bt._apply_hex(True)
    assert pump(bt, lambda: bt.hex_view.rows != [], timeout=5.0)
    bt._apply_hex(False)
    assert bt.hex_view.rows == []  # 끄면 비운다 (오프셋이 이어지지 않으므로)


def test_drag_boundary_changes_width_and_persists(tmp_path):
    path = tmp_path / "settings.json"
    term = make(config=Settings(), config_path=path)
    try:
        term._apply_hex(True)
        term.app.step()
        split = term.terminal_split
        before = term.hex_frame.rect.w
        x = split.split_x - 1
        term.app.dispatch(MouseEvent("down", 1, x, term.frame.rect.y + 2, 0, 0))
        term.app.dispatch(MouseEvent("move", 0, x - 8, term.frame.rect.y + 2, 0, 0))
        term.app.dispatch(MouseEvent("up", 1, x - 8, term.frame.rect.y + 2, 0, 0))
        term.app.step()
        assert term.hex_frame.rect.w == before + 8
        assert term.app.cursor_name(term.frame, split.split_x - 1, term.frame.rect.y + 2) == "resize_ew"
        ratio = split.ratio
    finally:
        term.port.close()
        term.app.close()
    assert store.load(path)[0].hex_split == round(ratio, 4)
