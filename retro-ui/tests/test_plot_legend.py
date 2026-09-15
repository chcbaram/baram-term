import pytest

from retroui import App, Button, HBox, Label, LivePlot, PlotLegend, VBox
from retroui.input.events import MouseEvent


@pytest.fixture
def app():
    try:
        a = App(headless=True, size=(60, 16), theme="mono")
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))
    yield a
    a.close()


def click(app, x, y):
    app.dispatch(MouseEvent("down", 1, x, y, 0, 0))
    app.dispatch(MouseEvent("up", 1, x, y, 0, 0))


def test_headerless_plot_starts_at_first_row(app):
    with_header = LivePlot("t")
    no_header = LivePlot(header=False)
    app.set_root(VBox(with_header, no_header))
    app.step()
    assert with_header.pixel_rect().y == with_header.rect.y + 1
    assert no_header.pixel_rect().y == no_header.rect.y
    assert no_header.pixel_rect().h == with_header.pixel_rect().h + 1


def test_legend_lists_series_and_click_toggles_visibility(app):
    plot = LivePlot(header=False)
    legend = PlotLegend(plot)
    button = Button("STOP", style="solid", color="error")
    app.set_root(VBox(HBox(legend, button, spacing=2), plot))
    app.step()
    changes = []
    plot.series_changed.connect(lambda: changes.append(1))
    ax = plot.add_series("ax")
    plot.add_series("ay")
    app.step()
    row = app.screen_text()[0]
    assert row.startswith("■ ax  ■ ay") and "STOP" in row  # 표시 뒤 한 칸: ■ 가 첫 글자를 덮지 않게
    assert legend.cursor == "hand" and len(changes) == 2

    click(app, legend.rect.x + 1, legend.rect.y)  # ■ax
    assert ax.visible is False and len(changes) == 3
    app.step()
    assert app.screen_text()[0].startswith("□ ax")
    click(app, legend.rect.x + 1, legend.rect.y)
    assert ax.visible is True

    plot.clear_series()
    app.step()
    assert "ax" not in app.screen_text()[0] and legend.cursor is None


def test_solid_button_fills_with_color(app):
    button = Button("STOP", style="solid", color="error")
    app.set_root(VBox(button, Label("x")))
    app.step()
    pal = app.theme.palette
    assert button.rect.h == 1
    assert app.buf.get(button.rect.x + 1, button.rect.y)[2] == pal.error
    button.set_color("ok")
    app.step()
    assert app.buf.get(button.rect.x + 1, button.rect.y)[2] == pal.ok
