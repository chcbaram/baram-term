import numpy as np
import pygame
import pytest

from retroui import App, Button, HBox, Label, LivePlot, Spacer, VBox

GREEN = (85, 255, 85)
PAD = 6


@pytest.fixture
def app():
    try:
        a = App(headless=True, size=(20, 6), theme="dos_blue", padding=PAD)
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))
    yield a
    a.close()


def px(app, x, y):
    return tuple(app.surface.get_at((x, y))[:3])


def test_surface_includes_padding_and_grid_keeps_size(app):
    cw, ch = app.fonts.cw, app.fonts.ch
    assert app.surface.get_size() == (20 * cw + 2 * PAD, 6 * ch + 2 * PAD)
    assert (app.cols, app.rows) == (20, 6)
    assert app.origin == (PAD, PAD)


def test_cells_are_drawn_inside_the_padding(app):
    app.set_root(VBox(Label("█", fg="white")))
    app.screen_text()
    bg = app.theme.palette.bg
    assert px(app, PAD - 1, PAD + 2) == bg  # 여백
    assert px(app, PAD + 1, PAD + 2) == (255, 255, 255)  # 첫 셀 (블록 문자)


def test_mouse_uses_grid_origin(app):
    clicks = []
    b = Button("Go", on_click=lambda: clicks.append(1))
    app.set_root(VBox(HBox(b, Spacer())))
    app.screen_text()
    cw, ch = app.fonts.cw, app.fonts.ch

    def click_at(x, y):
        for kind in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            app._handle_pygame_event(pygame.event.Event(kind, button=1, pos=(x, y)))

    click_at(PAD // 2, PAD // 2)  # 여백: 어떤 위젯도 아니다
    assert clicks == []
    click_at(PAD + cw + 1, PAD + ch // 2)  # 버튼 두 번째 셀
    assert clicks == [1]


def test_pixel_widgets_are_composited_at_the_origin(app):
    plot = LivePlot("P", y_range=(0.0, 1.0), update_hz=0)
    plot.add_series("a", color="light_green").extend(np.full(200, 0.5))
    app.set_root(VBox(plot))
    app.step()
    area = plot.pixel_rect()
    cw, ch = app.fonts.cw, app.fonts.ch
    h = area.h * ch
    x = PAD + area.x * cw + (area.w * cw) // 2
    y = PAD + area.y * ch + round(0.5 * (h - 1))
    assert GREEN in {px(app, x, yy) for yy in range(y - 1, y + 2)}


def test_font_size_change_keeps_padding(app):
    app.set_root(VBox(Spacer()))
    app.set_font_size(22)
    cw, ch = app.fonts.cw, app.fonts.ch
    assert app.surface.get_size() == (20 * cw + 2 * PAD, 6 * ch + 2 * PAD)
    assert app.origin == (PAD, PAD)
