import os
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest  # noqa: E402

from retroui import App, Button, HBox, Label, Spacer, VBox  # noqa: E402
from retroui.input.events import Key, KeyEvent, Mod, MouseEvent  # noqa: E402
from retroui.widgets.tooltip import Tooltip, wrap  # noqa: E402


@pytest.fixture
def app():
    try:
        a = App(title="t", size=(40, 10), headless=True)
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))
    a.tooltip_delay = 0.05
    yield a
    a.close()


def build(app, tip="the whole command", top=False):
    """매크로 막대처럼 화면 아래쪽에 있는 버튼 (top=True 면 맨 윗줄)."""
    button = Button("F1 cmd")
    button.tooltip = tip
    row = HBox(button, Label("x"))
    app.set_root(VBox(row, Spacer()) if top else VBox(Spacer(), row))
    app.ensure_layout()
    app.step()
    return button


def hover(app, widget, dx=1):
    app.dispatch(MouseEvent("move", 0, widget.rect.x + dx, widget.rect.y, 0, 0, Mod.NONE))


def settle(app, seconds=0.2):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.step()
        time.sleep(0.01)


def test_wrap_breaks_on_spaces_within_the_width():
    assert wrap("one two three", 7) == ["one two", "three"]


def test_wrap_keeps_a_long_word_whole():
    assert wrap("aaaaaaaaaa bb", 4) == ["aaaaaaaaaa", "bb"]


def test_wrap_counts_hangul_as_two_columns():
    assert wrap("한글 한글 한글", 9) == ["한글 한글", "한글"]


def test_tooltip_appears_only_after_the_delay(app):
    button = build(app)
    hover(app, button)
    app.step()
    assert not app.popups
    settle(app)
    assert len(app.popups) == 1
    assert isinstance(app.popups[0], Tooltip)


def test_tooltip_shows_the_full_text(app):
    button = build(app, "nvs set wifi 1234")
    hover(app, button)
    settle(app)
    assert any("nvs set wifi 1234" in row for row in app.screen_text())


def test_tooltip_sits_above_the_widget(app):
    button = build(app)
    hover(app, button)
    settle(app)
    assert app.popups[0].rect.bottom <= button.rect.y


def test_tooltip_drops_below_when_there_is_no_room_above(app):
    button = build(app, top=True)
    hover(app, button)
    settle(app)
    assert app.popups[0].rect.y >= button.rect.bottom


def test_moving_off_the_widget_closes_it(app):
    button = build(app)
    hover(app, button)
    settle(app)
    assert app.popups
    app.dispatch(MouseEvent("move", 0, button.rect.right + 2, button.rect.y, 0, 0, Mod.NONE))
    app.step()
    assert not app.popups


def test_a_key_closes_it(app):
    button = build(app)
    hover(app, button)
    settle(app)
    app.dispatch(KeyEvent(Key.ESCAPE, Mod.NONE, "escape"))
    assert not app.popups


def test_a_click_closes_it_and_still_reaches_the_button(app):
    button = build(app)
    clicked = []
    button.clicked.connect(lambda: clicked.append(1))
    hover(app, button)
    settle(app)
    app.dispatch(MouseEvent("down", 1, button.rect.x + 1, button.rect.y, 0, 0, Mod.NONE))
    app.dispatch(MouseEvent("up", 1, button.rect.x + 1, button.rect.y, 0, 0, Mod.NONE))
    assert not app.popups
    assert clicked


def test_widget_without_tooltip_shows_nothing(app):
    button = build(app, "")
    hover(app, button)
    settle(app)
    assert not app.popups


def test_no_tooltip_while_a_popup_is_open(app):
    from retroui import ListPopup

    button = build(app)
    popup = ListPopup(["Edit", "Clear"])
    popup._app = app
    app.open_popup(popup, 0, 0)
    hover(app, button)
    settle(app)
    assert [type(p).__name__ for p in app.popups] == ["ListPopup"]


def test_opening_a_popup_closes_a_showing_tooltip(app):
    from retroui import ListPopup

    button = build(app)
    hover(app, button)
    settle(app)
    assert any(isinstance(p, Tooltip) for p in app.popups)
    popup = ListPopup(["Edit"])
    popup._app = app
    app.open_popup(popup, 0, 0)
    assert not any(isinstance(p, Tooltip) for p in app.popups)


def test_tooltip_waits_again_after_the_popup_closes(app):
    from retroui import ListPopup

    button = build(app)
    popup = ListPopup(["Edit"])
    popup._app = app
    app.open_popup(popup, 0, 0)
    hover(app, button)
    settle(app)
    app.close_popup(popup)
    app.step()
    assert not app.popups, "메뉴를 닫은 직후에 툴팁이 바로 뜨면 안 된다"
    settle(app)
    assert any(isinstance(p, Tooltip) for p in app.popups)
