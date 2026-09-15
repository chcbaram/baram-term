import pytest

from retroui import App, Terminal, VBox
from retroui.input.events import IS_MAC, Key, KeyEvent, Mod, MouseEvent
from retroui.widgets.lineedit import clipboard_get, clipboard_put

COPY_MOD = Mod.META if IS_MAC else Mod.CTRL | Mod.SHIFT


@pytest.fixture
def app():
    try:
        a = App(headless=True, size=(30, 6), theme="mono")
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))
    yield a
    a.close()


def setup(app, **kw):
    t = Terminal(**kw)
    sent = []
    t.send.connect(sent.append)
    app.set_root(VBox(t))
    app.step()
    return t, sent


def drag(app, x0, y0, x1, y1):
    app.dispatch(MouseEvent("down", 1, x0, y0, 0, 0))
    app.dispatch(MouseEvent("move", 0, x1, y1, 0, 0))
    app.dispatch(MouseEvent("up", 1, x1, y1, 0, 0))


def click(app, x, y):
    app.dispatch(MouseEvent("down", 1, x, y, 0, 0))
    app.dispatch(MouseEvent("up", 1, x, y, 0, 0))


def test_drag_selects_across_lines_and_highlights(app):
    t, _ = setup(app)
    t.feed("hello world\r\nsecond line")
    drag(app, 6, 0, 5, 1)
    assert t.selected_text() == "world\nsecond"
    app.screen_text()
    pal = app.theme.palette
    assert app.buf.get(6, 0)[2] == pal.sel_bg
    assert app.buf.get(5, 0)[2] != pal.sel_bg
    assert app.buf.get(5, 1)[2] == pal.sel_bg and app.buf.get(6, 1)[2] != pal.sel_bg


def test_click_without_drag_clears_selection(app):
    t, _ = setup(app)
    t.feed("hello world")
    drag(app, 0, 0, 4, 0)
    assert t.selected_text() == "hello"
    click(app, 8, 0)
    assert t.selected_text() == ""


def test_double_click_selects_word(app):
    t, _ = setup(app)
    t.feed("[OK] uartInit() done")
    # 더블클릭 여부는 App 이 연속 클릭 시간/위치로 판단한다 (이벤트의 clicks 값은 덮어씀)
    click(app, 8, 0)
    click(app, 8, 0)
    assert t.selected_text() == "uartInit()"


def test_copy_shortcut_puts_text_on_clipboard_and_does_not_send(app):
    t, sent = setup(app)
    t.feed("cli# help")
    drag(app, 5, 0, 8, 0)
    clipboard_put("")
    app.dispatch(KeyEvent(Key.C, COPY_MOD, "c"))
    assert clipboard_get() == "help"
    assert sent == []


def test_plain_ctrl_c_still_goes_to_device(app):
    t, sent = setup(app)
    t.feed("running")
    drag(app, 0, 0, 3, 0)
    app.dispatch(KeyEvent(Key.C, Mod.CTRL, "c"))
    if IS_MAC:
        assert sent == [b"\x03"]  # macOS 는 Cmd+C 가 복사라 Ctrl+C 는 그대로 장치로
    else:
        assert sent == [b"\x03"]  # Ctrl+Shift 가 아니면 장치로


def test_selection_stays_on_same_text_when_new_lines_arrive(app):
    t, _ = setup(app, max_lines=3)
    for i in range(3):
        t.feed(f"line {i}\r\n")
    t.scroll(1)
    top = app.screen_text()[0]
    drag(app, 0, 0, 5, 0)
    selected = t.selected_text()
    assert selected == top.rstrip()[:6]
    for i in range(3, 400):  # 스크롤백 한도로 앞줄이 잘려도
        t.feed(f"line {i}\r\n")
    assert t.selected_text() in (selected, "")  # 같은 글자이거나, 잘려 나갔으면 빈 문자열


def test_select_all_and_wide_chars(app):
    t, _ = setup(app)
    t.feed("가나 abc\r\n끝")
    t.select_all()
    assert t.selected_text() == "가나 abc\n끝"
    drag(app, 1, 0, 2, 0)  # '가' 오른쪽 절반 ~ '나' 왼쪽 절반
    assert t.selected_text() == "가나"


def test_selection_skips_timestamp_gutter(app):
    t, _ = setup(app, show_timestamps=True, clock=lambda: 0.0)
    t.feed("abcdef")
    drag(app, 13, 0, 15, 0)
    assert t.selected_text() == "abc"
