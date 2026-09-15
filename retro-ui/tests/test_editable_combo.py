import pytest

from retroui import App, EditableComboBox, Label, ListPopup, VBox
from retroui.input.events import Key, KeyEvent, Mod, MouseEvent, TextEvent
from retroui.render.cellbuffer import Attr


@pytest.fixture
def app():
    try:
        a = App(headless=True, size=(40, 14), theme="mono")
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))
    yield a
    a.close()


def digits(text):
    return text == "" or text.isdigit()


def setup(app):
    cb = EditableComboBox(["9600", "115200"], "115200", validator=digits)
    app.set_root(VBox(cb, Label("below")))
    app.set_focus(cb)
    app.step()
    return cb


def click(app, x, y):
    app.dispatch(MouseEvent("down", 1, x, y, 0, 0))
    app.dispatch(MouseEvent("up", 1, x, y, 0, 0))


def test_typing_is_filtered_by_validator(app):
    cb = setup(app)
    cb.select_all()
    for ch in "2x50000":
        app.dispatch(TextEvent(ch))
    assert cb.text == "250000"
    row = app.screen_text()[0]
    assert "250000" in row and "▼" in row


def test_down_opens_list_and_choice_sets_text(app):
    cb = setup(app)
    app.dispatch(KeyEvent(Key.DOWN, Mod.NONE, ""))
    popup = app.popups[-1]
    assert isinstance(popup, ListPopup) and popup.selected == 1 and cb.is_open
    chosen = []
    cb.chosen.connect(chosen.append)
    popup.choose(0)
    assert cb.text == "9600" and not cb.is_open and app.focus is cb and chosen == ["9600"]


def test_click_arrow_toggles_list(app):
    cb = setup(app)
    click(app, cb.rect.right - 2, cb.rect.y)
    assert cb.is_open
    click(app, cb.rect.right - 2, cb.rect.y)
    assert not cb.is_open and not app.popups


def test_clickable_label_keeps_focus_and_underlines_on_hover(app):
    got = []
    cb = EditableComboBox(["1"], "1")
    port = Label("port", on_click=lambda: got.append("port"))
    plain = Label("plain")
    app.set_root(VBox(cb, port, plain))
    app.set_focus(cb)
    app.step()
    assert port.cursor == "hand" and plain.cursor is None

    click(app, 1, port.rect.y)
    assert got == ["port"] and app.focus is cb  # 글자를 눌러도 포커스는 그대로

    app.dispatch(MouseEvent("move", 0, 1, port.rect.y, 0, 0))
    app.screen_text()
    assert app.buf.get(1, port.rect.y)[3] & Attr.UNDERLINE
    click(app, 1, plain.rect.y)
    assert got == ["port"]
