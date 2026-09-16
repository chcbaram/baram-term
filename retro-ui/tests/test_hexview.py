import pytest

from retroui import App, HexView, Label, VBox
from retroui.input.events import WheelEvent
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
