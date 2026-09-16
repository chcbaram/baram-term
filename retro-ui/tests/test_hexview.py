import pytest

from retroui import App, HexView, Label, VBox
from retroui.input.events import Mod, MouseEvent, WheelEvent
from retroui.widgets.hexview import row_width


@pytest.fixture
def app():
    try:
        a = App(headless=True, size=(50, 10), theme="mono")
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))
    yield a
    a.close()


def setup(app, **kw):
    view = HexView(**kw)
    app.set_root(VBox(view))
    app.step()
    return view


def rows(app):
    return app.screen_text()


def test_rows_show_offset_direction_hex_and_ascii(app):
    view = setup(app)
    view.append(b"cli# help\r\n", "rx")
    view.append(b"info\r", "tx")
    app.step()
    assert view.bytes_per_row == 8 and view.ascii_column
    text = rows(app)
    assert text[0].startswith("00000000 RX 63 6C 69 23 20 68 65 6C")
    assert text[0].rstrip().endswith("cli# hel")
    assert text[1].startswith("00000008 RX 70 0D 0A")
    assert text[1].rstrip().endswith("p..")
    # 방향이 바뀌면 새 줄에서 시작한다
    assert text[2].startswith("0000000B TX 69 6E 66 6F 0D") and text[2].rstrip().endswith("info.")


def test_bytes_per_row_follows_width():
    assert row_width(8, True) == 45 and row_width(16, True) == 77 and row_width(8, False) == 35
    view = HexView()
    assert view.fit(90) == (16, True)
    assert view.fit(50) == (8, True)
    assert view.fit(40) == (4, True)
    assert view.fit(20) == (4, False)


def test_resize_keeps_bytes_and_offsets(app):
    view = setup(app)
    view.append(bytes(range(0x10)), "rx")
    assert [r[0] for r in view.rows] == [0, 8]
    view.set_bytes_per_row(4)
    assert [(r[0], bytes(r[2])) for r in view.rows][:2] == [(0, bytes(range(4))), (4, bytes(range(4, 8)))]
    assert len(view.rows) == 4
    view.set_bytes_per_row(16)
    assert len(view.rows) == 1 and bytes(view.rows[0][2]) == bytes(range(0x10))


def test_old_rows_are_dropped_but_offsets_keep_growing(app):
    view = setup(app, max_rows=4)
    view.trim_slack = 2
    for _ in range(20):
        view.append(b"12345678", "rx")
    assert len(view.rows) <= 6 and view.next_offset == 160
    assert view.rows[-1][0] == 152


def test_wheel_scrolls_and_new_data_keeps_the_view(app):
    view = setup(app)
    for i in range(40):
        view.append(bytes([i]) * 8, "rx")
    assert view.scroll_offset == 0 and view.view_top() == len(view.rows) - view.rows_visible

    app.dispatch(WheelEvent(0, 3, 2, 2, 0, 0))  # 위로
    up = view.scroll_offset
    assert up > 0
    view.append(b"xxxxxxxx", "rx")
    assert view.scroll_offset == up + 1  # 보던 자리 유지
    view.scroll(-100)
    assert view.scroll_offset == 0


def test_pause_holds_position_and_resume_follows(app):
    view = setup(app)
    for i in range(20):
        view.append(bytes([i]) * 8, "rx")
    view.set_paused(True)
    top = view.view_top()
    view.append(b"abcdefgh", "rx")
    assert view.view_top() == top
    view.set_paused(False)
    assert view.scroll_offset == 0 and view.view_top() == len(view.rows) - view.rows_visible


def test_pause_freezes_the_rows_on_screen(app):
    """화면이 덜 찼을 때도 정지하면 새 줄이 나오지 않는다 (데이터는 뒤에서 계속 쌓인다)."""
    view = setup(app)
    view.append(b"AAAA", "rx")
    app.step()
    before = app.screen_text()
    view.set_paused(True)
    view.append(b"BBBB", "rx")  # 덜 찬 마지막 줄에도 덧붙지 않는다
    view.append(b"CCCCCCCC", "rx")
    app.step()
    assert view.shown_rows == 1 and app.screen_text() == before
    assert len(view.rows) == 3 and view.next_offset == 16  # 데이터는 쌓인다

    # 스크롤바는 전체 데이터 기준이라 손잡이가 줄어든다 (데이터가 들어오고 있다는 표시)
    assert view.scrollbar.total == len(view.rows) == 3
    # 정지 순간의 줄만 닫는다: 그 뒤 조각들은 평소처럼 한 줄을 채운다
    assert [bytes(row[2]) for row in view.rows] == [b"AAAA", b"BBBBCCCC", b"CCCC"]

    view.set_paused(False)
    app.step()
    assert view.shown_rows == 3
    text = app.screen_text()
    assert text[1].startswith("00000004 RX 42 42 42 42") and "BBBB" in text[1]


def test_scrolling_while_paused_moves_through_new_data(app):
    view = setup(app)
    for i in range(20):
        view.append(bytes([0x41 + i % 26]) * 8, "rx")
    view.set_paused(True)
    top = view.view_top()
    for i in range(10):
        view.append(b"ZZZZZZZZ", "rx")
    assert view.view_top() == top and view.scrollbar.total == 30

    view.scroll(-5)  # 정지 중에도 아래(최신)로 내려가 새 줄을 볼 수 있다
    assert view.view_top() == top + 5
    view.scroll(50)
    assert view.view_top() == 0  # 맨 위까지
    view.set_paused(False)
    assert view.view_top() == len(view.rows) - view.rows_visible


def test_clear_resets_offsets(app):
    view = setup(app)
    view.append(b"abc")
    view.clear()
    assert view.rows == [] and view.next_offset == 0
    view.append(b"z")
    assert view.rows[0][0] == 0
    app.set_root(VBox(view, Label("below")))
    app.step()
    assert app.screen_text()[0].startswith("00000000 RX 7A")


def hex_x(view, i=0):
    return view.rect.x + 8 + 1 + 2 + 1 + 3 * i


def ascii_x(view, i=0):
    return view.rect.x + 8 + 1 + 2 + 1 + 3 * view.bytes_per_row - 1 + 2 + i


def press(app, x, y, mod=Mod.NONE):
    app.dispatch(MouseEvent("down", 1, x, y, 0, 0, mod))
    app.dispatch(MouseEvent("up", 1, x, y, 0, 0, mod))


def test_click_selects_a_byte_in_either_column(app):
    view = setup(app)
    changes = []
    view.selection_changed.connect(lambda: changes.append(view.selection))
    view.append(b"cli# help", "rx")
    app.step()
    press(app, hex_x(view, 2), view.rect.y)
    assert view.selection == (2, 2) and view.selected_bytes() == b"i"
    press(app, ascii_x(view, 4), view.rect.y)  # ASCII 칸을 눌러도 같은 규칙
    assert view.selection == (4, 4) and view.selected_bytes() == b" "
    assert changes[-1] == (4, 4)

    app.screen_text()
    pal = app.theme.palette
    assert app.buf.get(hex_x(view, 4), view.rect.y)[2] == pal.sel_bg  # 16진수와
    assert app.buf.get(ascii_x(view, 4), view.rect.y)[2] == pal.sel_bg  # ASCII 를 같이 강조


def test_drag_and_shift_click_select_a_range(app):
    view = setup(app)
    view.append(b"cli# help\r\n", "rx")
    app.step()
    app.dispatch(MouseEvent("down", 1, hex_x(view, 1), view.rect.y, 0, 0))
    app.dispatch(MouseEvent("move", 0, hex_x(view, 2), view.rect.y + 1, 0, 0))  # 다음 줄까지
    app.dispatch(MouseEvent("up", 1, hex_x(view, 2), view.rect.y + 1, 0, 0))
    assert view.selection == (1, 10) and view.selected_bytes() == b"li# help\r\n"

    press(app, hex_x(view, 3), view.rect.y, Mod.SHIFT)  # 처음 고른 자리(1)부터 다시
    assert view.selection == (1, 3) and view.selected_bytes() == b"li#"


def test_click_on_empty_area_clears_selection(app):
    view = setup(app)
    view.append(b"ab", "rx")
    app.step()
    press(app, hex_x(view, 1), view.rect.y)
    assert view.selection == (1, 1)
    press(app, hex_x(view, 5), view.rect.y)  # 그 줄에 없는 바이트 자리
    assert view.selection is None and view.selected_bytes() == b""


def test_selection_follows_offsets_and_drops_when_trimmed(app):
    view = setup(app, max_rows=4)
    view.trim_slack = 2
    view.append(b"abcdefgh", "rx")
    app.step()
    press(app, hex_x(view, 0), view.rect.y)
    assert view.selection == (0, 0)
    for _ in range(3):
        view.append(b"12345678", "rx")
    assert view.selection == (0, 0)  # 아직 남아 있다
    for _ in range(10):
        view.append(b"12345678", "rx")
    assert view.selection is None  # 잘려 나가면 선택도 사라진다
