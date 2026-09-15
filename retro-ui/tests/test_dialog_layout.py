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


@pytest.mark.parametrize("theme", ["mono", "dos_blue"])
def test_dialog_buttons_share_the_widest_width(theme):
    app = make_app(theme)
    try:
        app.set_root(VBox(Spacer()))
        dialog = message_box(app, "Plot time window", "30 seconds", ("OK", "Cancel"))
        app.screen_text()
        ok, cancel = dialog.buttons
        assert ok.rect.w == cancel.rect.w == len("Cancel") + 4
        # 글자는 넓어진 버튼 가운데에
        row = app.screen_text()[ok.rect.y + (1 if ok.rect.h == 3 else 0)]
        text_x = row.index("OK", ok.rect.x)
        assert text_x - ok.rect.x == (ok.rect.w - 2) // 2
    finally:
        app.close()


def test_dialog_button_row_is_centered():
    app = make_app("mono")
    try:
        app.set_root(VBox(Spacer()))
        dialog = message_box(app, "A long dialog title here", "x", ("OK", "Cancel"))
        app.screen_text()
        ok, cancel = dialog.buttons
        left = ok.rect.x - (dialog.rect.x + 1)
        right = (dialog.rect.right - 1) - cancel.rect.right
        assert abs(left - right) <= 1
    finally:
        app.close()
