import time
from types import SimpleNamespace

import pytest
from retroui import TerminalScreen
from retroui.input.events import Key, KeyEvent, Mod, TextEvent

from baram_term import i18n
from baram_term.app import BaramTerm
from baram_term.completion import CommandCatalog, current_input
from baram_term.serial_port import PortSettings


def test_catalog_learns_from_help_output_split_and_colored():
    c = CommandCatalog()
    c.feed("cli# help\r\n\r\n---------- cmd list ---------\r\nHELP\r\nIN")
    assert c.commands == []
    c.feed("FO\r\n\x1b[32mLOG\x1b[0m\r\n-----------------------------\r\n\n\rcli# ")
    assert c.commands == ["help", "info", "log"]
    assert c.matches("I") == ["info"]
    assert c.matches("") == ["help", "info", "log"]


def test_catalog_ignores_blocks_that_are_not_command_lists():
    c = CommandCatalog()
    c.feed("---------- cmd list ---------\r\nnot a command!\r\nHELP\r\n-----------------------------\r\n")
    assert c.commands == []


def fake_terminal(text):
    screen = TerminalScreen(80, 10)
    screen.feed(text)
    return SimpleNamespace(screen=screen)


def test_current_input_reads_prompt_line():
    assert current_input(fake_terminal("boot\r\n\n\rcli# he")) == ("he", 5)
    assert current_input(fake_terminal("\n\rcli# ")) == ("", 5)
    assert current_input(fake_terminal("\n\rcli# md 0x08")) is None  # 인자 입력 중
    assert current_input(fake_terminal("[OK] log line")) is None  # 프롬프트 줄이 아님


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


def cursor_line(term):
    scr = term.terminal.screen
    return scr.line_text(scr.cy)


def type_text(term, text):
    for ch in text:
        term.app.dispatch(TextEvent(ch))


def key(term, k):
    term.app.dispatch(KeyEvent(k, Mod.NONE, ""))


def learn_commands(term):
    term.connect()
    assert pump(term, lambda: cursor_line(term) == "cli#")
    type_text(term, "help")
    key(term, Key.RETURN)
    assert pump(term, lambda: bool(term.completer.catalog.commands))
    assert pump(term, lambda: cursor_line(term) == "cli#")


def test_tab_without_command_list_shows_hint(bt):
    bt.connect()
    assert pump(bt, lambda: cursor_line(bt) == "cli#")
    key(bt, Key.TAB)
    assert "run help once" in "\n".join(bt.app.screen_text())


def test_single_match_completes_immediately(bt):
    learn_commands(bt)
    type_text(bt, "r")
    assert pump(bt, lambda: current_input(bt.terminal) == ("r", 5))
    key(bt, Key.TAB)
    assert pump(bt, lambda: cursor_line(bt) == "cli# reset")
    assert not bt.completer.is_open


def test_ambiguous_prefix_opens_list_that_follows_typing(bt):
    learn_commands(bt)
    type_text(bt, "s")
    assert pump(bt, lambda: current_input(bt.terminal) == ("s", 5))
    key(bt, Key.TAB)
    assert bt.completer.is_open
    assert bt.completer.popup.items == ["sensor", "status"]
    assert bt.app.focus is bt.terminal  # 목록이 떠도 입력은 터미널로
    term = bt.terminal
    assert bt.completer.popup.rect.x == term.rect.x + term.gutter + 5  # 상자가 명령어 첫 글자 열에서 시작

    type_text(bt, "t")  # 장치 에코가 오면 목록이 좁혀진다
    assert pump(bt, lambda: bt.completer.is_open and bt.completer.popup.items == ["status"])
    key(bt, Key.RETURN)
    assert pump(bt, lambda: cursor_line(bt) == "cli# status")
    assert not bt.completer.is_open


def test_arrow_select_and_escape(bt):
    learn_commands(bt)
    key(bt, Key.TAB)  # 빈 입력: 모든 명령
    assert bt.completer.is_open and len(bt.completer.popup.items) >= 5
    key(bt, Key.DOWN)
    assert bt.completer.popup.selected == 1
    key(bt, Key.ESCAPE)
    assert not bt.completer.is_open
    assert cursor_line(bt) == "cli#"


def test_completion_can_be_turned_off(bt):
    learn_commands(bt)
    bt._apply_complete(False)
    type_text(bt, "s")
    assert pump(bt, lambda: current_input(bt.terminal) == ("s", 5))
    key(bt, Key.TAB)  # 끄면 Tab 은 그대로 장치로 간다
    assert not bt.completer.is_open
