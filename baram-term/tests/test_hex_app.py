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


def byte_pos(term, offset):
    """오프셋이 그려진 화면 좌표. 한 줄 바이트 수는 패널 폭에 따라 달라지므로 줄을 찾아서 계산한다."""
    term.app.ensure_layout()
    view = term.hex_view
    top = view.view_top()
    for row_index in range(top, len(view.rows)):
        start, _direction, data = view.rows[row_index]
        if start <= offset < start + len(data):
            x = view.rect.x + 8 + 1 + 2 + 1 + 3 * (offset - start)
            return x, view.rect.y + (row_index - top)
    raise AssertionError(f"offset {offset} is not on screen")


def test_selection_shows_info_and_copy(bt, monkeypatch):
    copied = []
    monkeypatch.setattr("baram_term.app.clipboard_put", copied.append)
    bt._apply_hex(True)
    bt.hex_view.append(b"cli# help", "rx")
    bt.app.step()
    assert bt.hex_info.text == "" and not bt.hex_copy_button.enabled

    x, y = byte_pos(bt, 2)
    bt.app.dispatch(MouseEvent("down", 1, x, y, 0, 0))
    bt.app.dispatch(MouseEvent("up", 1, x, y, 0, 0))
    assert bt.hex_info.text == "@00000002  69  105  'i'" and bt.hex_copy_button.enabled

    x2, y2 = byte_pos(bt, 5)  # 줄이 바뀔 수도 있다
    bt.app.dispatch(MouseEvent("down", 1, x, y, 0, 0))
    bt.app.dispatch(MouseEvent("move", 0, x2, y2, 0, 0))
    bt.app.dispatch(MouseEvent("up", 1, x2, y2, 0, 0))
    info = bt.hex_info.text
    assert "4 bytes" in info and info.startswith("@00000002") and len(info) <= bt.hex_info.rect.w

    click(bt, bt.hex_copy_button)
    assert copied == ["69 23 20 68"] and bt.app.focus is bt.terminal
    assert "copied 4 bytes as hex" in "\n".join(bt.app.screen_text())


def test_clearing_the_view_clears_the_info_line(bt):
    bt._apply_hex(True)
    bt.hex_view.append(b"ab", "rx")
    bt.app.step()
    x, y = byte_pos(bt, 0)
    bt.app.dispatch(MouseEvent("down", 1, x, y, 0, 0))
    bt.app.dispatch(MouseEvent("up", 1, x, y, 0, 0))
    assert bt.hex_info.text
    click(bt, bt.hex_clear_button)
    assert bt.hex_info.text == "" and not bt.hex_copy_button.enabled


def hex_lines(term):
    """화면에서 HEX 패널의 데이터 줄만 잘라낸다 (버튼 글자가 있는 조작줄은 뺀다)."""
    view = term.hex_view
    x, y = view.rect.x, view.rect.y
    return [line[x : x + view.rect.w] for line in term.app.screen_text()[y : y + view.rect.h]]


def test_stop_freezes_the_panel_even_when_not_full(bt):
    bt._apply_hex(True)
    bt.hex_view.append(b"AAAA", "rx")
    bt.app.step()
    before = hex_lines(bt)

    click(bt, bt.hex_run_button)
    assert bt.hex_view.paused and bt.hex_run_button.text == "START"
    bt.hex_view.append(b"BBBB", "rx")
    bt.hex_view.append(b"CCCCCCCC", "rx")
    bt.app.step()
    assert hex_lines(bt) == before  # 정지 중에는 화면이 그대로
    assert bt.hex_view.next_offset == 16  # 데이터는 계속 쌓인다

    click(bt, bt.hex_run_button)
    bt.app.step()
    assert bt.hex_run_button.text == "STOP"
    assert "42 42 42 42" in "\n".join(hex_lines(bt))  # START 를 누르면 밀린 줄이 보인다
