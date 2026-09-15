import pytest

from retroui import App, Button, ComboBox, Dialog, Label, LineEdit, ListPopup, Spacer, VBox, message_box
from retroui.input.events import Key, KeyEvent, Mod, MouseEvent, TextEvent


@pytest.fixture
def app():
    try:
        a = App(headless=True, size=(40, 20))
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))
    yield a
    a.close()


def key(k, mod=Mod.NONE):
    return KeyEvent(k, mod, "")


def click(app, cx, cy):
    app.dispatch(MouseEvent("down", 1, cx, cy, 0, 0))
    app.dispatch(MouseEvent("up", 1, cx, cy, 0, 0))


def test_combobox_keyboard_and_list_popup(app):
    changes = []
    cb = ComboBox(["9600", "115200", "921600"], index=1, on_change=lambda i, t: changes.append(t))
    app.set_root(VBox(cb, Spacer()))
    assert app.screen_text()[0].startswith(" 115200")

    app.dispatch(key(Key.DOWN))
    assert cb.text == "921600" and changes == ["921600"]

    app.dispatch(key(Key.SPACE))
    assert isinstance(app.focus, ListPopup) and app.focus.selected == 2
    app.dispatch(key(Key.UP))
    app.dispatch(key(Key.RETURN))
    assert cb.text == "115200"
    assert not app.popups and app.focus is cb


def test_combobox_mouse_open_and_pick(app):
    cb = ComboBox(["9600", "115200", "921600"], index=1)
    app.set_root(VBox(cb, Spacer()))
    app.screen_text()
    click(app, cb.rect.x + 1, cb.rect.y)
    popup = app.popups[-1]
    click(app, popup.rect.x + 2, popup.rect.y + 1)  # 첫 항목
    assert cb.text == "9600" and not app.popups


def test_combobox_click_again_closes(app):
    cb = ComboBox(["a", "b"])
    app.set_root(VBox(cb, Spacer()))
    app.screen_text()
    click(app, cb.rect.x, cb.rect.y)
    assert app.popups
    click(app, cb.rect.x, cb.rect.y)
    assert not app.popups


def test_long_list_scrolls(app):
    cb = ComboBox([f"COM{i}" for i in range(30)], visible_rows=5)
    app.set_root(VBox(cb, Spacer()))
    app.screen_text()
    app.dispatch(key(Key.SPACE))
    popup = app.focus
    app.dispatch(key(Key.END))
    assert popup.selected == 29 and popup.top == 25
    assert "COM29" in "\n".join(app.screen_text())


def test_set_items_keeps_current_text(app):
    cb = ComboBox(["/dev/ttyUSB0", "/dev/ttyUSB1"], index=1)
    app.set_root(VBox(cb))
    cb.set_items(["/dev/ttyACM0", "/dev/ttyUSB1"])
    assert cb.text == "/dev/ttyUSB1"
    cb.set_items(["/dev/ttyACM0"])
    assert cb.text == "/dev/ttyACM0"


def test_dialog_is_modal_and_enter_escape_restore_focus(app):
    results = []
    base = Button("Base", on_click=lambda: results.append("base"))
    app.set_root(VBox(base, Spacer()))
    app.screen_text()

    name = LineEdit("COM3")
    dialog = Dialog("포트", VBox(Label("포트 이름"), name), on_result=results.append)
    dialog.open(app)
    assert app.focus is name

    click(app, base.rect.x + 1, base.rect.y + 1)  # 모달: 바깥 클릭 무시
    assert results == [] and dialog.is_open

    app.dispatch(TextEvent("0"))
    assert name.text == "COM30"
    app.dispatch(key(Key.RETURN))  # 받을 곳 없는 LineEdit 의 Enter 는 기본 버튼으로
    assert results == [0] and not dialog.is_open
    assert app.focus is base

    dialog.open(app)
    app.dispatch(key(Key.ESCAPE))
    assert results == [0, 1]


def test_dialog_tab_stays_inside(app):
    base = Button("Base")
    app.set_root(VBox(base, Spacer()))
    app.screen_text()
    name = LineEdit()
    dialog = Dialog("포트", VBox(name))
    dialog.open(app)
    seen = []
    for _ in range(4):
        app.dispatch(key(Key.TAB))
        seen.append(app.focus)
    assert seen == [dialog.buttons[0], dialog.buttons[1], name, dialog.buttons[0]]


def test_dialog_button_click(app):
    results = []
    app.set_root(VBox(Spacer()))
    dialog = message_box(app, "알림", "연결이 끊겼습니다\n다시 연결할까요?", ("예", "아니오"), on_result=results.append)
    text = "\n".join(app.screen_text())
    assert "연결이 끊겼습니다" in text and "다시 연결할까요?" in text
    no = dialog.buttons[1]
    click(app, no.rect.x + 1, no.rect.y + 1)
    assert results == [1]
