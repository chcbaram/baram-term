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


def test_padding_moves_text_caret_and_clicks_together(app):
    """padding 은 그리기만이 아니라 클릭 위치와 IME 후보창 좌표(caret_cell)까지 함께 옮긴다.

    하나라도 빠지면 글자와 클릭 지점이 한 칸 어긋난다. 기본값은 0 이고, ComboBox 와 나란히
    놓이는 칸(포트 설정의 Address)에만 1 을 준다.
    """
    e = setup(app, text="abc", padding=1)
    app.set_focus(e)
    app.screen_text()

    assert app.screen_text()[0].startswith(" abc")
    assert e.caret_cell() == (e.rect.x + 1 + 3, e.rect.y)
    assert e.index_at(e.rect.x + 1) == 0  # 첫 글자 칸
    assert e.index_at(e.rect.x + 2) == 1


def test_no_padding_by_default(app):
    e = setup(app, text="abc")
    assert e.padding == 0
    assert app.screen_text()[0].startswith("abc")


def test_caret_is_not_drawn_over_a_selection(app):
    """선택 칸에 캐럿 반전을 덧칠하면 그 칸만 색이 튀어 선택에서 빠진 것처럼 보였다."""
    e = setup(app, text="abc")
    app.set_focus(e)
    app.dispatch(key(Key.A, PRIMARY))  # 전체 선택
    app.screen_text()

    pal = app.theme.palette
    for i in range(3):
        ch, _fg, bg, attr = app.buf.get(e.rect.x + i, e.rect.y)
        assert bg == pal.sel_bg, (i, ch)
        assert not attr & Attr.REVERSE, (i, ch)


def test_padding_is_not_part_of_the_selection(app):
    """왼쪽 여백은 글자가 아니다. 전체를 골라도 여백 칸은 선택 색으로 칠하지 않는다.

    한때 "첫 글자가 빠져 보인다" 를 피하려고 여백까지 칠했는데, 그 증상의 원인은 여백이
    아니라 선택 위에 덧그리던 캐럿이었다. 여백을 칠하면 거기에도 고른 내용이 있는 것처럼
    보인다 (브라우저·OS 기본 입력칸도 안쪽 여백은 칠하지 않는다).
    """
    e = setup(app, text="abc", padding=1)
    app.set_focus(e)
    app.dispatch(key(Key.A, PRIMARY))  # 전체 선택
    app.screen_text()

    pal = app.theme.palette
    pad_bg = app.buf.get(e.rect.x, e.rect.y)[2]
    assert pad_bg == pal.input_bg, "여백은 입력칸 배경 그대로"
    for i in range(3):  # 글자는 모두 선택 색
        assert app.buf.get(e.rect.x + 1 + i, e.rect.y)[2] == pal.sel_bg, i
