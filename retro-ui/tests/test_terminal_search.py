import pytest

from retroui import App, Terminal, VBox


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
    app.set_root(VBox(t))
    app.step()
    return t


def test_matches_are_smartcase_and_use_cell_columns(app):
    t = setup(app)
    t.feed("가나 Error\r\nerror again\r\nno")
    t.set_search("error")
    assert t.search_matches() == [(0, 5, 10), (1, 0, 5)]
    t.set_search("Error")
    assert t.search_matches() == [(0, 5, 10)]
    t.set_search("나")
    assert t.search_matches() == [(0, 2, 4)]  # 와이드 문자는 두 칸
    t.set_search("")
    assert t.search_matches() == []


def test_current_match_is_revealed_and_highlighted(app):
    t = setup(app)
    t.feed("\r\n".join(f"line {i}" for i in range(40)))
    t.set_search("line 3")
    matches = t.search_matches()
    assert [m[0] for m in matches] == [3, *range(30, 40)]

    t.set_search_current(matches[0])
    assert t.scroll_offset > 0
    rows = app.screen_text()
    row = next(r for r, text in enumerate(rows) if text.startswith("line 3"))
    pal = app.theme.palette
    assert app.buf.get(0, row)[2] == pal.sel_bg and app.buf.get(6, row)[2] != pal.sel_bg

    t.set_search_current(matches[-1])  # 맨 아래 줄: 스크롤이 바닥으로 돌아온다
    assert t.scroll_offset == 0
    app.screen_text()
    assert app.buf.get(0, 5)[2] == pal.sel_bg  # line 39 (지금 가리키는 일치)
    assert app.buf.get(0, 4)[2] == pal.hover_bg  # line 38 (다른 일치)
    assert app.buf.get(0, 3)[2] == pal.hover_bg
    assert pal.hover_bg != pal.sel_bg


def test_visible_match_does_not_scroll(app):
    t = setup(app)
    t.feed("\r\n".join(f"row {i}" for i in range(20)))
    t.set_search("row 17")
    (match,) = t.search_matches()
    t.set_search_current(match)
    assert t.scroll_offset == 0


def test_matches_use_absolute_lines_after_scrollback_trim_and_clear_resets(app):
    t = setup(app, max_lines=20)
    t.feed("\r\n".join(f"row {i}" for i in range(400)))
    assert t.screen.dropped > 0
    t.set_search("row 399")
    (match,) = t.search_matches()
    assert match[0] - t.screen.dropped == len(t.screen.lines) - 1
    t.set_search_current(match)
    t.clear()
    assert t.search_current is None
