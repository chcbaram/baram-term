import pytest

from retroui import App, LineEdit, VBox
from retroui.input.events import IS_MAC, CompositionEvent, Key, KeyEvent, Mod, MouseEvent, TextEvent
from retroui.render.cellbuffer import Attr

PRIMARY = Mod.META if IS_MAC else Mod.CTRL


@pytest.fixture
def app():
    try:
        a = App(headless=True, size=(30, 6))
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))
    yield a
    a.close()


def key(k, mod=Mod.NONE):
    return KeyEvent(k, mod, "")


def setup(app, **kw):
    e = LineEdit(**kw)
    app.set_root(VBox(e))
    app.step()
    return e


def test_typing_cursor_and_backspace(app):
    e = setup(app)
    app.dispatch(TextEvent("ab한"))
    assert e.text == "ab한" and e.cursor == 3
    app.dispatch(key(Key.LEFT))
    app.dispatch(key(Key.BACKSPACE))
    assert e.text == "a한" and e.cursor == 1
    app.dispatch(key(Key.END))
    assert e.cursor == 2
    app.dispatch(key(Key.HOME))
    app.dispatch(key(Key.DELETE))
    assert e.text == "한"


def test_shift_selection_is_replaced_by_typing(app):
    e = setup(app, text="hello")
    app.dispatch(key(Key.HOME))
    app.dispatch(key(Key.RIGHT, Mod.SHIFT))
    app.dispatch(key(Key.RIGHT, Mod.SHIFT))
    assert e.selection() == (0, 2)
    app.dispatch(TextEvent("J"))
    assert e.text == "Jllo"


def test_select_all_copy_paste(app):
    e = setup(app, text="abc")
    app.dispatch(key(Key.A, PRIMARY))
    app.dispatch(key(Key.C, PRIMARY))
    app.dispatch(key(Key.END))
    app.dispatch(key(Key.V, PRIMARY))
    assert e.text == "abcabc"


def test_preedit_is_underlined_and_caret_follows_it(app):
    e = setup(app)
    app.dispatch(TextEvent("가"))
    app.dispatch(CompositionEvent("나", 1))
    lines = app.screen_text()
    assert lines[0].startswith("가나")
    assert app.buf.get(2, 0)[3] & Attr.UNDERLINE
    assert not app.buf.get(0, 0)[3] & Attr.UNDERLINE
    assert e.text == "가"
    assert e.caret_cell() == (4, 0)


def test_long_text_scrolls_to_keep_caret_visible(app):
    e = setup(app)
    app.dispatch(TextEvent("한" * 20))
    app.screen_text()
    assert e.scroll > 0
    assert e.caret_cell() == (29, 0)
    app.dispatch(key(Key.HOME))
    app.screen_text()
    assert e.scroll == 0 and e.caret_cell() == (0, 0)


def test_mouse_click_places_cursor_by_display_columns(app):
    e = setup(app, text="a한b")
    for cx, expected in ((0, 0), (1, 1), (2, 2), (3, 2), (10, 3)):
        app.dispatch(MouseEvent("down", 1, cx, 0, 0, 0))
        app.dispatch(MouseEvent("up", 1, cx, 0, 0, 0))
        assert e.cursor == expected, cx


def test_enter_submits_and_clears(app):
    sent = []
    e = setup(app, clear_on_submit=True, on_submit=sent.append)
    app.dispatch(TextEvent("ls -al"))
    app.dispatch(key(Key.RETURN))
    assert sent == ["ls -al"] and e.text == ""


def test_history_recall(app):
    e = setup(app, clear_on_submit=True, history=True, on_submit=lambda t: None)
    for cmd in ("boot", "reset"):
        app.dispatch(TextEvent(cmd))
        app.dispatch(key(Key.RETURN))
    app.dispatch(key(Key.UP))
    assert e.text == "reset"
    app.dispatch(key(Key.UP))
    assert e.text == "boot"
    app.dispatch(key(Key.DOWN))
    assert e.text == "reset"
    app.dispatch(key(Key.DOWN))
    assert e.text == ""


def test_max_length_and_validator(app):
    e = setup(app, max_length=3, validator=lambda t: t == "" or t.isdigit())
    app.dispatch(TextEvent("12a"))
    assert e.text == ""
    app.dispatch(TextEvent("1234"))
    assert e.text == "123"


def test_tab_during_composition_commits_to_previous_widget(app):
    e1 = LineEdit()
    e2 = LineEdit()
    app.set_root(VBox(e1, e2))
    app.step()
    assert app.focus is e1
    app.dispatch(CompositionEvent("한", 1))
    app.dispatch(key(Key.TAB))
    assert app.focus is e2
    assert e1.text == "한"
    app.dispatch(TextEvent("한"))  # macOS 가 뒤늦게 보내는 확정: 새 위젯에 들어가면 안 된다
    assert e2.text == ""


def test_click_during_composition_commits_before_moving_focus(app):
    e1 = LineEdit()
    e2 = LineEdit()
    app.set_root(VBox(e1, e2))
    app.step()
    app.dispatch(CompositionEvent("글", 1))
    app.dispatch(MouseEvent("down", 1, e2.rect.x, e2.rect.y, 0, 0))
    app.dispatch(MouseEvent("up", 1, e2.rect.x, e2.rect.y, 0, 0))
    assert app.focus is e2
    assert e1.text == "글" and e2.text == ""
