import pytest

from retroui import App, LineEdit, ListPopup, VBox
from retroui.input.events import TextEvent


@pytest.fixture
def app():
    try:
        a = App(headless=True, size=(30, 12))
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))
    yield a
    a.close()


def test_popup_without_focus_keeps_typing_in_widget(app):
    edit = LineEdit()
    app.set_root(VBox(edit))
    app.step()
    popup = ListPopup(["alpha", "beta"])
    app.open_popup(popup, 0, 1, focus=False)
    assert app.focus is edit and popup.is_open
    app.dispatch(TextEvent("x"))
    assert edit.text == "x"
    popup.close()
    assert app.focus is edit


def test_set_items_keeps_selection_and_reposition_resizes(app):
    edit = LineEdit()
    app.set_root(VBox(edit))
    app.step()
    popup = ListPopup(["sensor", "status", "system"], selected=1)
    app.open_popup(popup, 2, 2, focus=False)
    popup.set_items(["status", "system"], keep="status")
    assert popup.items[popup.selected] == "status"
    hint = popup.effective_hint()
    app.reposition_popup(popup, 2, 2, hint.pref_w, hint.pref_h)
    assert popup.rect.h == 2 + 2
    popup.set_items(["system"], keep="status")
    assert popup.selected == 0
