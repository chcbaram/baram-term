import pytest

from retroui import App, Button, HBox, Spacer, VBox
from retroui.input.events import MouseEvent
from retroui.render.boxdraw import EDGE_HEAVY, EDGE_INSET, EDGE_LIGHT
from retroui.render.cellbuffer import attr_fill


@pytest.fixture
def app():
    try:
        a = App(headless=True, size=(30, 8), theme="mono")
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))
    yield a
    a.close()


def cell(app, x, y):
    return app.buf.get(x, y)


def test_mono_theme_uses_black_background_and_d2coding(app):
    app.set_root(VBox(Spacer()))
    app.screen_text()
    assert app.buf.get(0, 0)[2] == (0, 0, 0)
    assert "D2Coding" in app.fonts.path


def test_mono_theme_keeps_plot_series_in_color(app):
    series = app.theme.palette.series
    assert any(len(set(c)) > 1 for c in series[:3])


def test_focused_box_button_keeps_border_and_fills(app):
    ok = Button("OK")
    no = Button("No")
    app.set_root(VBox(HBox(ok, no, Spacer(), spacing=1)))
    lines = app.screen_text()
    pal = app.theme.palette
    assert ok.rect.h == 3 and ok.rect.w == 6
    assert " OK " in lines[1] and " No " in lines[1]

    corner = cell(app, ok.rect.x, ok.rect.y)
    assert corner[0] == EDGE_HEAVY[0] and corner[1] == pal.border_focus
    assert corner[2] == pal.bg and attr_fill(corner[3]) == pal.hover_bg  # 바깥은 배경, 선 안쪽만 채움
    assert cell(app, ok.rect.x + 2, ok.rect.y + 1)[2] == pal.hover_bg

    other = cell(app, no.rect.x, no.rect.y)
    assert other[0] == EDGE_LIGHT[0] and other[1] == pal.border and attr_fill(other[3]) == pal.button_bg


def test_focused_box_button_pixels_are_inset_and_do_not_bleed(app):
    ok = Button("OK")
    app.set_root(VBox(Spacer(size=1, stretch=0), HBox(Spacer(size=1, stretch=0), ok, Spacer())))
    app.screen_text()
    pal = app.theme.palette
    cw, ch = app.fonts.cw, app.fonts.ch
    s = 2  # 굵은 선, 헤드리스 scale 1
    x0, y0 = ok.rect.x * cw, ok.rect.y * ch
    x1 = ok.rect.right * cw
    top_y = y0 + round(ch * EDGE_INSET)
    bottom_y = y0 + 2 * ch + round(ch * (1 - EDGE_INSET))
    left_x = x0 + cw // 2 - s // 2
    mid_x = (x0 + x1) // 2
    mid_y = y0 + ch + ch // 2

    def px(x, y):
        return tuple(app.surface.get_at((x, y))[:3])

    assert px(mid_x, top_y) == pal.border_focus
    assert px(mid_x, top_y - 1) == pal.bg  # 윗변 바깥으로 번지지 않음
    assert px(mid_x, top_y + s) == pal.hover_bg
    assert px(mid_x, bottom_y - 1) == pal.border_focus
    assert px(mid_x, bottom_y) == pal.bg
    assert px(left_x, mid_y) == pal.border_focus
    assert px(left_x - 1, mid_y) == pal.bg
    assert px(x1, mid_y) == pal.bg
    # 보이는 버튼 높이가 셀 3줄보다 확실히 작다
    assert bottom_y - top_y < 2 * ch


def test_box_button_click_on_border_and_label_row(app):
    clicks = []
    b = Button("OK", on_click=lambda: clicks.append(1))
    app.set_root(VBox(HBox(b, Spacer())))
    app.screen_text()
    for dy in (0, 1, 2):
        app.dispatch(MouseEvent("down", 1, b.rect.x + 1, b.rect.y + dy, 0, 0))
        app.dispatch(MouseEvent("up", 1, b.rect.x + 1, b.rect.y + dy, 0, 0))
    assert clicks == [1, 1, 1]


def test_fill_style_can_still_be_forced(app):
    b = Button("OK", style="fill")
    app.set_root(VBox(HBox(b, Spacer())))
    lines = app.screen_text()
    assert b.rect.h == 1
    assert lines[0].startswith("► OK ◄")


def test_hover_brightens_border_and_press_fills_with_selection(app):
    ok = Button("OK")
    no = Button("No")
    app.set_root(VBox(HBox(ok, no, Spacer(), spacing=1)))
    app.screen_text()
    pal = app.theme.palette
    assert cell(app, no.rect.x, no.rect.y)[1] == pal.border

    app.dispatch(MouseEvent("move", 0, no.rect.x + 2, no.rect.y + 1, 0, 0))
    app.screen_text()
    assert no.hovered
    assert cell(app, no.rect.x, no.rect.y)[1] == pal.border_focus
    assert cell(app, no.rect.x + 1, no.rect.y + 1)[2] == pal.button_bg

    app.dispatch(MouseEvent("down", 1, no.rect.x + 2, no.rect.y + 1, 0, 0))
    app.screen_text()
    assert cell(app, no.rect.x + 1, no.rect.y + 1)[2] == pal.sel_bg
    assert cell(app, no.rect.x, no.rect.y)[0] == EDGE_HEAVY[0]
    assert cell(app, no.rect.x, no.rect.y)[1] == pal.border_focus


def test_mono_is_the_default_theme():
    try:
        a = App(headless=True, size=(10, 4))
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))
    try:
        assert a.theme.name == "mono"
    finally:
        a.close()


def test_set_font_size_keeps_grid_and_rescales_surface(app):
    b = Button("OK")
    app.set_root(VBox(HBox(b, Spacer())))
    app.screen_text()
    small = (app.fonts.cw, app.fonts.ch)
    app.set_font_size(24)
    lines = app.screen_text()
    assert app.fonts.px == 24
    assert (app.cols, app.rows) == (30, 8)
    assert app.fonts.cw > small[0] and app.fonts.ch > small[1]
    assert app.surface.get_size() == (30 * app.fonts.cw, 8 * app.fonts.ch)
    assert " OK " in lines[1]


def test_bundled_d2coding_is_used(app):
    assert "retroui/assets/fonts" in app.fonts.path.replace("\\", "/")


def test_font_size_shortcuts_with_equals_and_minus(app):
    import pygame

    from retroui.input.events import IS_MAC, KeyEvent, Mod

    primary = Mod.META if IS_MAC else Mod.CTRL
    app.add_shortcut("Primary+=", lambda: app.set_font_size(app.fonts.size + 1))
    app.add_shortcut("Primary+-", lambda: app.set_font_size(app.fonts.size - 1))
    app.set_root(VBox(Spacer()))
    base = app.fonts.size
    app.dispatch(KeyEvent(pygame.K_EQUALS, primary, "="))
    app.dispatch(KeyEvent(pygame.K_EQUALS, primary, "="))
    assert app.fonts.size == base + 2
    app.dispatch(KeyEvent(pygame.K_MINUS, primary, "-"))
    assert app.fonts.size == base + 1
    assert (app.cols, app.rows) == (30, 8)
