import time

import numpy as np
import pytest

from retroui import App, Label, LivePlot, VBox

GREEN = (85, 255, 85)


@pytest.fixture
def app():
    try:
        a = App(headless=True, size=(40, 12), theme="dos_blue")
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))
    yield a
    a.close()


def plot_px(app, plot, fx, value):
    """플롯 영역 안 x 비율 fx 위치에서 value 가 그려질 픽셀 좌표."""
    area = plot.pixel_rect()
    cw, ch = app.fonts.cw, app.fonts.ch
    w, h = area.w * cw, area.h * ch
    lo, hi = plot.y_range
    x = area.x * cw + int((w - 1) * fx)
    y = area.y * ch + round((hi - value) * (h - 1) / (hi - lo))
    return x, y


def colors_near(app, x, y):
    return {tuple(app.surface.get_at((x, yy))[:3]) for yy in range(y - 1, y + 2)}


def settle(app, n=3):
    for _ in range(n):
        time.sleep(0.005)
        app.step()


def test_constant_series_is_drawn_at_expected_height(app):
    plot = LivePlot("POS", y_range=(0.0, 1.0), update_hz=1000)
    s = plot.add_series("a", color="light_green")
    s.extend(np.full(200, 0.5))
    app.set_root(VBox(plot))
    settle(app)
    assert GREEN in colors_near(app, *plot_px(app, plot, 0.5, 0.5))
    assert GREEN not in colors_near(app, *plot_px(app, plot, 0.5, 0.9))


def test_title_legend_and_axis_labels(app):
    plot = LivePlot("POS", y_range=(0.0, 1.0), update_hz=1000)
    plot.add_series("act").extend(np.zeros(10))
    app.set_root(VBox(plot))
    settle(app)
    lines = app.screen_text()
    assert lines[0].startswith("POS")
    assert lines[0].rstrip().endswith("■act")
    text = "\n".join(lines)
    assert "1.0" in text and "0.0" in text


def test_pause_freezes_and_resume_catches_up(app):
    plot = LivePlot("POS", y_range=(0.0, 1.0), update_hz=1000)
    s = plot.add_series("a", color="light_green")
    s.extend(np.full(200, 0.2))
    app.set_root(VBox(plot))
    settle(app)

    plot.set_paused(True)
    s.extend(np.full(200, 0.9))
    settle(app)
    assert GREEN not in colors_near(app, *plot_px(app, plot, 0.95, 0.9))
    assert "PAUSED" in app.screen_text()[0]

    plot.set_paused(False)
    settle(app)
    assert GREEN in colors_near(app, *plot_px(app, plot, 0.95, 0.9))


def test_cell_updates_elsewhere_do_not_erase_plot(app):
    plot = LivePlot("POS", y_range=(0.0, 1.0), update_hz=0)  # 폴링 끔: 다시 그리지 않아도 남아 있어야 한다
    s = plot.add_series("a", color="light_green")
    s.extend(np.full(100, 0.5))
    label = Label("tick 0")
    app.set_root(VBox(label, plot))
    settle(app)
    for i in range(3):
        label.set_text(f"tick {i + 1}")
        settle(app, 1)
    assert GREEN in colors_near(app, *plot_px(app, plot, 0.5, 0.5))


def test_idle_plot_does_not_redraw_without_new_data(app):
    plot = LivePlot("POS", y_range=(0.0, 1.0), update_hz=1000)
    plot.add_series("a").extend(np.zeros(10))
    app.set_root(VBox(plot))
    settle(app)
    frames = app.frame_count
    settle(app, 5)
    assert app.frame_count == frames
