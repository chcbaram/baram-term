import pytest

from retroui import App, Label, Spacer, VBox, message_box


def make_app(theme):
    try:
        return App(headless=True, size=(40, 20), theme=theme)
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))


@pytest.mark.parametrize(
    "theme, rows_below_button",
    [
        ("mono", 0),  # 박스 버튼: 테두리 선이 셀 안쪽에 있어 아래 여백 줄 없이도 약 1.2줄이 비어 보인다
        ("dos_blue", 1),  # 한 줄 버튼: 아래 여백 1줄로 위아래 대칭
    ],
)
def test_dialog_bottom_space_depends_on_button_style(theme, rows_below_button):
    app = make_app(theme)
    try:
        app.set_root(VBox(Spacer()))
        dialog = message_box(app, "About", "line one\nline two", ("Close",))
        app.screen_text()
        button = dialog.buttons[0]
        border_row = dialog.rect.bottom - 1
        assert border_row - button.rect.bottom == rows_below_button
        # 위쪽은 두 테마 모두 테두리 다음 여백 1줄 뒤에 내용이 시작한다
        assert dialog.body.rect.y == dialog.rect.y + 2
    finally:
        app.close()


def test_box_margin_per_side():
    app = make_app("dos_blue")
    try:
        label = Label("x")
        box = VBox(label, margin=(2, 1, 0, 3))
        app.set_root(VBox(box, Spacer()))
        app.screen_text()
        assert (label.rect.x, label.rect.y) == (2, 1)
        hint = box.size_hint()
        assert (hint.pref_w, hint.pref_h) == (1 + 2, 1 + 1 + 3)
        assert box.margins == (2, 1, 0, 3)
    finally:
        app.close()
