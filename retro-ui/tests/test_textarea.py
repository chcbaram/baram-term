import pytest

from retroui import App, TextArea, VBox
from retroui.input.events import CompositionEvent, Key, KeyEvent, Mod, MouseEvent, TextEvent, WheelEvent
from retroui.render.cellbuffer import Attr


@pytest.fixture
def app():
    try:
        a = App(headless=True, size=(30, 6), theme="mono")
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))
    yield a
    a.close()


def setup(app, text=""):
    area = TextArea(text)
    changes = []
    area.changed.connect(changes.append)
    app.set_root(VBox(area))
    app.set_focus(area)
    app.step()
    return area, changes


def key(app, k, mod=Mod.NONE):
    app.dispatch(KeyEvent(k, mod, ""))


def test_typing_and_newlines(app):
    area, changes = setup(app)
    for ch in "reset":
        app.dispatch(TextEvent(ch))
    key(app, Key.RETURN)
    for ch in "log on":
        app.dispatch(TextEvent(ch))
    assert area.lines == ["reset", "log on"] and area.text == "reset\nlog on"
    assert (area.row, area.col) == (1, 6) and changes[-1] == "reset\nlog on"
    assert app.screen_text()[0].startswith("reset")


def test_backspace_joins_lines_and_delete_merges(app):
    area, _ = setup(app, "ab\ncd")
    area.move_to(1, 0)
    key(app, Key.BACKSPACE)
    assert area.lines == ["abcd"] and (area.row, area.col) == (0, 2)
    area.move_to(0, 2)
    key(app, Key.DELETE)
    assert area.lines == ["abd"]


def test_selection_with_shift_keys_and_rows(app):
    area, _ = setup(app, "one\ntwo\nthree")
    area.move_to(0, 1)
    key(app, Key.DOWN, Mod.SHIFT)
    key(app, Key.END, Mod.SHIFT)
    assert area.selected_text() == "ne\ntwo"
    assert area.selected_rows() == (0, 1)
    key(app, Key.RIGHT)  # 선택 해제
    assert area.selection() is None and area.selected_rows() is None


def test_selected_rows_ignores_a_trailing_line_start(app):
    area, _ = setup(app, "one\ntwo\nthree")
    area.move_to(0, 0)
    area.move_to(1, 0, extend=True)
    assert area.selected_rows() == (0, 0)  # 두 번째 줄 첫 칸에서 끝나면 그 줄은 빼고


def test_mouse_drag_selects(app):
    area, _ = setup(app, "one\ntwo\nthree")
    app.dispatch(MouseEvent("down", 1, area.rect.x + 1, area.rect.y, 0, 0))
    app.dispatch(MouseEvent("move", 0, area.rect.x + 2, area.rect.y + 1, 0, 0))
    app.dispatch(MouseEvent("up", 1, area.rect.x + 2, area.rect.y + 1, 0, 0))
    assert area.selected_text() == "ne\ntw" and area.selected_rows() == (0, 1)

    app.dispatch(MouseEvent("down", 1, area.rect.x + 1, area.rect.y, 0, 0))
    app.dispatch(MouseEvent("up", 1, area.rect.x + 1, area.rect.y, 0, 0))
    assert area.selection() is None  # 끌지 않은 클릭


def test_clipboard_copy_and_paste(app, monkeypatch):
    clip = []
    monkeypatch.setattr("retroui.widgets.textarea.clipboard_put", clip.append)
    monkeypatch.setattr("retroui.widgets.textarea.clipboard_get", lambda: "x\ny")
    area, _ = setup(app, "one\ntwo")
    area.select_all()
    # 복사/붙여넣기 조합키는 OS 마다 다르다 (mac 은 Cmd, 그 외는 Ctrl): 둘 다 보내 본다
    for mod in (Mod.META, Mod.CTRL):
        app.dispatch(KeyEvent(Key.C, mod, ""))
    assert clip == ["one\ntwo"]

    area.move_to(0, 0)
    for mod in (Mod.META, Mod.CTRL):
        app.dispatch(KeyEvent(Key.V, mod, ""))
    assert area.lines[0] == "x" and "one" in area.text


def test_paste_multiline_text_through_insert(app):
    area, _ = setup(app, "start\nend")
    area.move_to(0, 5)
    area.insert("\nmiddle 1\nmiddle 2")
    assert area.lines == ["start", "middle 1", "middle 2", "end"]
    assert (area.row, area.col) == (2, 8)


def test_scrolling_follows_cursor_and_wheel(app):
    area, _ = setup(app, "\n".join(f"line {i}" for i in range(30)))
    area.move_to(20, 0)
    assert area.scroll_row == 20 - area.rows_visible + 1
    app.dispatch(WheelEvent(0, 3, area.rect.x + 1, area.rect.y + 1, 0, 0))
    assert area.scroll_row < 20 - area.rows_visible + 1
    assert area.scrollbar.total == 30


def test_ime_preedit_is_shown_then_committed(app):
    area, _ = setup(app, "")
    app.dispatch(CompositionEvent("ㅎ", 1))
    assert area.preedit == "ㅎ" and area.text == ""
    app.step()
    assert "ㅎ" in app.screen_text()[0]
    app.dispatch(TextEvent("한"))
    assert area.text == "한" and area.preedit == ""


def test_marked_row_is_highlighted(app):
    area, _ = setup(app, "one\ntwo")
    area.marked_row = 1
    app.set_focus(None)
    app.step()
    pal = app.theme.palette
    assert app.buf.get(area.rect.x, area.rect.y + 1)[2] == pal.hover_bg
    assert app.buf.get(area.rect.x, area.rect.y)[2] == pal.input_bg


def test_horizontal_scroll_marks_cut_lines(app):
    long_line = "sensor start " + "x" * 40
    area, _ = setup(app, f"reset\n#wait 2000\n{long_line}")
    assert area.scroll_col == 0
    app.step()
    assert app.screen_text()[1].startswith("#wait")

    area.move_to(2, len(long_line))  # 커서가 오른쪽 끝으로 가면 화면이 가로로 밀린다
    app.step()
    assert area.scroll_col > 0
    rows = app.screen_text()
    assert rows[0].startswith("‹") and rows[1].startswith("‹")  # 앞이 잘렸다는 표시

    area.move_to(2, 0)
    app.step()
    assert area.scroll_col == 0 and not app.screen_text()[0].startswith("‹")


def test_caret_is_not_drawn_over_a_selection(app):
    """선택한 칸에 캐럿 반전을 덧칠하면 그 칸만 더 하얗게 떠서 선택에서 빠진 것처럼 보였다.

    오른쪽에서 왼쪽으로 고르면 캐럿이 선택 범위의 첫 글자에 놓여 특히 눈에 띈다.
    """
    area, _ = setup(app, "reset")
    area.move_to(0, 5)
    area.move_to(0, 0, extend=True)
    app.screen_text()

    pal = app.theme.palette
    for i in range(5):
        ch, _fg, bg, attr = app.buf.get(area.rect.x + i, area.rect.y)
        assert bg == pal.sel_bg, (i, ch)
        assert not attr & Attr.REVERSE, (i, ch)
