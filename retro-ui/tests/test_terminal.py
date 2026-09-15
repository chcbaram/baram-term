import pygame
import pytest

from retroui import App, VBox
from retroui.input.events import Key, KeyEvent, Mod, TextEvent, WheelEvent
from retroui.theme import LIGHT_GREEN, LIGHT_RED
from retroui.widgets.terminal import HighlightRule, Terminal, TerminalScreen


def scr(cols=40, rows=10, **kw):
    return TerminalScreen(cols, rows, **kw)


def texts(s):
    return [s.line_text(i) for i in range(len(s.lines))]


def test_crlf_and_cursor():
    s = scr()
    s.feed("abc\r\ndef")
    assert texts(s) == ["abc", "def"]
    assert (s.cx, s.cy) == (3, 1)


def test_bare_lf_returns_to_line_start_by_default():
    s = scr()
    s.feed("ab\ncd")
    assert texts(s) == ["ab", "cd"]
    s2 = scr(lf_implies_cr=False)
    s2.feed("ab\ncd")
    assert texts(s2) == ["ab", "  cd"]


def test_firmware_prompt_uses_lf_cr():
    s = scr()
    s.feed("boot ok\n\rcli# ")
    assert texts(s) == ["boot ok", "cli#"]
    assert s.cx == 5


def test_firmware_backspace_sequence():
    s = scr()
    s.feed("cli# help")
    s.feed("\b \b\x1b[1P")
    assert texts(s) == ["cli# hel"] and s.cx == 8


def test_firmware_insert_in_middle_and_delete_at_cursor():
    s = scr()
    s.feed("cli# hel\x1b[3D")
    assert s.cx == 5
    s.feed("\x1b[4hX\x1b[4l")
    assert texts(s) == ["cli# Xhel"] and s.cx == 6
    s.feed("\x1b[1D\x1b[1P")
    assert texts(s) == ["cli# hel"]


def test_escape_split_across_feeds():
    s = scr()
    s.feed("\x1b[3")
    s.feed("1mE\x1b[0mx")
    line = s.lines[0]
    assert line[0] == ("E", (1, None, 0))
    assert line[1][1] == (None, None, 0)


def test_sgr_bold_bright_and_reset():
    s = scr()
    s.feed("\x1b[1;32mOK\x1b[0m")
    assert s.lines[0][0][1] == (2, None, 1)
    assert s.style == (None, None, 0)


def test_erase_line_and_screen():
    s = scr(rows=3)
    s.feed("hello world\x1b[6D\x1b[K")
    assert texts(s) == ["hello"]
    s.feed("\r\nx\r\ny\x1b[2J\x1b[H")
    assert all(t == "" for t in texts(s)[-3:])
    assert (s.cx, s.cy) == (0, s.top)


def test_wrap_and_wide_chars():
    s = scr(cols=5)
    s.feed("abcdefg")
    assert texts(s) == ["abcde", "fg"]
    w = scr(cols=4)
    w.feed("가나다")
    assert texts(w) == ["가나", "다"]


def test_tab_stops_and_cursor_position():
    s = scr()
    s.feed("Name\t\t: X")
    assert texts(s) == ["Name            : X"]
    s.feed("\r\n\x1b[1;3HZ")
    assert s.line_text(s.top)[2] == "Z"


def test_cursor_visibility():
    s = scr()
    s.feed("\x1b[?25l")
    assert not s.cursor_visible
    s.feed("\x1b[?25h")
    assert s.cursor_visible


def test_scrollback_is_trimmed_and_cursor_stays_valid():
    s = scr(rows=5, max_lines=10)
    for i in range(1000):
        s.feed(f"line {i}\r\n")
    assert len(s.lines) <= 10 + 5 + 256 + 1
    assert s.dropped > 0
    assert s.line_text(s.cy - 1) == "line 999"


def test_unknown_sequences_are_skipped():
    s = scr()
    s.feed("a\x1b]0;title\x07b\x1b[?1049hc\x1b(Bd")
    assert texts(s) == ["abcBd"] or texts(s) == ["abcd"]


@pytest.fixture
def app():
    try:
        a = App(headless=True, size=(40, 8))
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))
    yield a
    a.close()


def setup_term(app, **kw):
    t = Terminal(**kw)
    sent = []
    t.send.connect(sent.append)
    app.set_root(VBox(t))
    app.step()
    return t, sent


def test_widget_renders_and_highlights_firmware_tags(app):
    t, _ = setup_term(app)
    t.rules = [HighlightRule.of(r"\[OK\]", LIGHT_GREEN), HighlightRule.of(r"\[E_\]", LIGHT_RED, bold=True)]
    t.feed("[OK] uartInit()\r\n[E_] canOpen()\r\n\x1b[34m[OK]\x1b[0m blue\r\ncli# ")
    lines = app.screen_text()
    assert lines[0].startswith("[OK] uartInit()")
    assert app.buf.get(1, 0)[1] == LIGHT_GREEN
    assert app.buf.get(5, 0)[1] != LIGHT_GREEN  # 태그 밖은 기본색
    assert app.buf.get(1, 1)[1] == LIGHT_RED
    assert app.buf.get(1, 2)[1] != LIGHT_GREEN  # 펌웨어가 준 ANSI 색 우선
    assert lines[3].startswith("cli#")


def test_widget_keys_are_translated_for_firmware_cli(app):
    t, sent = setup_term(app)
    for ev in (
        KeyEvent(Key.UP, Mod.NONE, "up"),
        KeyEvent(Key.HOME, Mod.NONE, "home"),
        KeyEvent(Key.END, Mod.NONE, "end"),
        KeyEvent(Key.BACKSPACE, Mod.NONE, "backspace"),
        KeyEvent(Key.DELETE, Mod.NONE, "delete"),
        KeyEvent(Key.RETURN, Mod.NONE, "return"),
        KeyEvent(pygame.K_c, Mod.CTRL, "c"),
    ):
        app.dispatch(ev)
    app.dispatch(TextEvent("가"))
    assert sent == [b"\x1b[A", b"\x1b[1~", b"\x1b[4~", b"\x08", b"\x7f", b"\r", b"\x03", "가".encode()]
    assert app.focus is t


def test_scroll_view_is_kept_when_new_data_arrives(app):
    t, sent = setup_term(app)
    for i in range(30):
        t.feed(f"log {i}\r\n")
    app.screen_text()
    app.dispatch(WheelEvent(0, 2, 1, 1, 0, 0))
    assert t.scroll_offset == 2 * t.wheel_lines  # OS 마다 기본 줄 수가 다르다
    top_before = app.screen_text()[1]
    t.feed("new line\r\n")
    assert app.screen_text()[1] == top_before
    app.dispatch(TextEvent("x"))  # 입력하면 맨 아래로
    assert t.scroll_offset == 0


def test_timestamp_gutter(app):
    t, _ = setup_term(app, show_timestamps=True, clock=lambda: 1_700_000_000.25)
    t.feed("hello")
    line = app.screen_text()[0]
    assert line[8:13] == ".250 " and line[13:18] == "hello"


def test_extended_colors_256_and_truecolor():
    s = scr()
    s.feed("\x1b[38;2;60;61;62mA\x1b[48;5;240mB\x1b[38;5;196mC\x1b[38;5;3mD\x1b[0mE")
    line = s.lines[0]
    assert line[0][1] == ((60, 61, 62), None, 0)
    assert line[1][1] == ((60, 61, 62), (88, 88, 88), 0)  # 240 -> 회색 단계
    assert line[2][1][0] == (255, 0, 0)  # 196 -> 색 큐브의 빨강
    assert line[3][1][0] == 3  # 0..15 는 ANSI 색 번호 그대로
    assert line[4][1] == (None, None, 0)


def test_truecolor_is_drawn_by_widget(app):
    t, _ = setup_term(app)
    t.feed("\x1b[38;2;60;60;60mX\x1b[0m")
    app.screen_text()
    assert app.buf.get(0, 0)[1] == (60, 60, 60)
