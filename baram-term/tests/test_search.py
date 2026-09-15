import time

import pygame
import pytest
from retroui.input.events import IS_MAC, Key, KeyEvent, Mod, TextEvent

from baram_term import i18n
from baram_term.app import BaramTerm
from baram_term.search import SearchBar
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


def pump(term, cond, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        term.app.step()
        if cond():
            return True
        time.sleep(0.01)
    return False


def open_search(term):
    term.app.dispatch(KeyEvent(pygame.K_a, Mod.CTRL, "a"))
    term.app.dispatch(KeyEvent(pygame.K_SLASH, Mod.NONE, "/"))
    return term.search


def type_text(term, text):
    for ch in text:
        term.app.dispatch(TextEvent(ch))


def fill(term):
    # 0, 50, 100, 150 번째 줄에만 marker
    lines = [f"{i:03d} marker here" if i % 50 == 0 else f"{i:03d} [OK] boot step" for i in range(200)]
    term.terminal.feed("\r\n".join(lines) + "\r\n")


def current_line(term):
    t = term.terminal
    return t.screen.line_text(t.search_current[0] - t.screen.dropped)


def test_find_walks_matches_from_newest(bt):
    fill(bt)
    bar = open_search(bt)
    assert isinstance(bar, SearchBar) and bar.is_open and bt.app.focus is bar.edit
    t = bt.terminal  # 그리기 전에 열어도 터미널 오른쪽 위에 붙는다
    assert t.rect.w > 0 and bar.rect.right == t.rect.right and bar.rect.y == t.rect.y

    type_text(bt, "marker")
    assert bar.count.text == "4/4" and current_line(bt).startswith("150")

    bt.app.dispatch(KeyEvent(Key.RETURN, Mod.NONE, ""))
    assert bar.count.text == "3/4" and current_line(bt).startswith("100")
    assert bt.terminal.scroll_offset > 0
    assert "100 marker here" in "\n".join(bt.app.screen_text())

    bt.app.dispatch(KeyEvent(Key.RETURN, Mod.SHIFT, ""))
    assert bar.count.text == "4/4"
    bt.app.dispatch(KeyEvent(Key.DOWN, Mod.NONE, ""))
    assert bar.count.text == "1/4" and current_line(bt).startswith("000")  # 끝에서 돈다

    type_text(bt, "X")  # 대문자가 섞이면 대소문자 구분
    assert bar.count.text == "none"


def test_escape_closes_and_returns_focus(bt):
    fill(bt)
    bar = open_search(bt)
    type_text(bt, "marker")
    bt.app.dispatch(KeyEvent(Key.ESCAPE, Mod.NONE, ""))
    assert not bar.is_open and bt.search is None
    assert bt.app.focus is bt.terminal and bt.terminal.search_current is None


def test_search_input_is_not_sent_and_tab_does_not_complete(bt):
    bt.connect()
    assert pump(bt, lambda: "cli#" in "\n".join(bt.app.screen_text()))
    time.sleep(0.05)
    bt.app.step()
    before = bt.port.tx_bytes
    open_search(bt)
    type_text(bt, "cli")
    bt.app.dispatch(KeyEvent(Key.TAB, Mod.NONE, ""))
    bt.app.dispatch(KeyEvent(Key.RETURN, Mod.NONE, ""))
    time.sleep(0.1)
    bt.app.step()
    assert bt.port.tx_bytes == before and not bt.completer.is_open
    assert "/" in bt.search.count.text  # 프롬프트 줄들에서 찾았다


def test_new_lines_update_count_and_reopen_keeps_query(bt):
    fill(bt)
    bar = open_search(bt)
    type_text(bt, "marker")
    assert bar.count.text == "4/4"
    bt.terminal.feed("200 marker again\r\n")
    bt._update_status()
    assert bar.count.text == "4/5"  # 보던 일치는 그대로
    bt.app.dispatch(KeyEvent(Key.ESCAPE, Mod.NONE, ""))

    bar = open_search(bt)
    assert bar.edit.text == "marker" and bar.count.text == "5/5"


@pytest.mark.skipif(not IS_MAC, reason="Cmd+F 는 macOS 에서만")
def test_cmd_f_opens_search_on_mac(bt):
    bt.app.dispatch(KeyEvent(pygame.K_f, Mod.META, "f"))
    assert bt.search is not None and bt.search.is_open
