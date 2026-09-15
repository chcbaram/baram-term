import pytest

from retroui import App, Dialog, FileDialog, Label, VBox, i18n, message_box, set_language


@pytest.fixture(autouse=True)
def keep_language():
    before = i18n.language()
    yield
    i18n.set_language(before)


@pytest.fixture
def app():
    try:
        a = App(headless=True, size=(60, 20), theme="mono")
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))
    a.set_root(VBox(Label("root")))
    yield a
    a.close()


def test_dialog_default_buttons_follow_language(app):
    set_language("en")
    assert [b.text for b in Dialog("t", Label("body")).buttons] == ["OK", "Cancel"]
    set_language("ko")
    assert [b.text for b in Dialog("t", Label("body")).buttons] == ["확인", "취소"]
    assert [b.text for b in message_box(app, "t", "body").buttons] == ["확인"]
    assert [b.text for b in Dialog("t", Label("body"), ("Go",)).buttons] == ["Go"]  # 직접 준 글자가 우선


def test_file_dialog_strings_follow_language_with_overrides(tmp_path):
    set_language("en")
    d = FileDialog("Save log", directory=tmp_path, text={"save": "Start"})
    assert d.text["folder"] == "Folder" and d.text["yes"] == "Yes"
    assert [b.text for b in d.buttons] == ["Start", "Cancel"]
    set_language("ko")
    d = FileDialog("열기", directory=tmp_path, mode="open")
    assert d.text["up"] == "▲ 위로" and [b.text for b in d.buttons] == ["열기", "취소"]


def test_language_detection(monkeypatch):
    monkeypatch.delenv("LC_MESSAGES", raising=False)
    monkeypatch.delenv("LANG", raising=False)
    monkeypatch.setenv("LC_ALL", "ko_KR.UTF-8")
    assert i18n.detect_language() == "ko"
    set_language("fr")  # 모르는 언어는 환경에서 정한다
    assert i18n.language() == "ko"
    monkeypatch.setenv("LC_ALL", "en_US.UTF-8")
    assert i18n.detect_language() == "en"


def test_every_language_has_every_key():
    keys = set(i18n.STRINGS["en"])
    for lang, table in i18n.STRINGS.items():
        assert set(table) == keys, lang
