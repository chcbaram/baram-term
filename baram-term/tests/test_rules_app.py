import pytest
from retroui.input.events import Key, KeyEvent, Mod, TextEvent
from retroui.theme import LIGHT_RED, YELLOW

from baram_term import i18n
from baram_term import settings as store
from baram_term.app import BaramTerm
from baram_term.serial_port import PortSettings
from baram_term.settings import Settings


def make(**kw):
    i18n.set_language("en")
    try:
        return BaramTerm(PortSettings(port="demo://"), headless=True, size=(110, 36), **kw)
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))


@pytest.fixture
def bt():
    term = make()
    yield term
    term.port.close()
    term.app.close()


def type_text(term, text):
    for ch in text:
        term.app.dispatch(TextEvent(ch))


def user_rules(term):
    """기본 규칙 앞에 붙은 사용자 규칙만."""
    return term.terminal.rules[: len(term.terminal.rules) - 4]


def test_add_rule_through_the_dialogs(tmp_path):
    path = tmp_path / "settings.json"
    term = make(config=Settings(), config_path=path)
    try:
        rules_dialog = term.open_rules_dialog()
        assert rules_dialog.listing.items == []

        edit = term.ask_rule(None, lambda entry: None)  # 추가 버튼과 같은 흐름
        assert term.app.focus is edit.pattern_edit and not edit.buttons[0].enabled  # 빈 정규식
        assert "enter a regular expression" in edit.error.text
        edit.finish(1)

        rules_dialog.entries.append(r"red bold|\bTIMEOUT\b")
        rules_dialog.listing.set_items([r"red      bold  \bTIMEOUT\b"])
        rules_dialog.finish(0)

        assert term.config.rules == [r"red bold|\bTIMEOUT\b"]
        rules = user_rules(term)
        assert len(rules) == 1 and rules[0].fg == LIGHT_RED and rules[0].bold
        assert rules[0].pattern.search("boot TIMEOUT now")
    finally:
        term.port.close()
        term.app.close()
    assert store.load(path)[0].rules == [r"red bold|\bTIMEOUT\b"]


def test_edit_dialog_validates_and_previews(bt):
    edit = bt.ask_rule("yellow|retry=\\d+", lambda entry: None)
    assert edit.pattern_edit.text == "retry=\\d+" and edit.color_combo.text == "yellow"
    assert edit.buttons[0].enabled and edit.error.text == ""
    marks = edit.preview.colors_at()
    start = edit.preview.text.index("retry=3")
    assert marks[start] == (YELLOW, False)  # 예시 줄에서 색이 입혀진다

    edit.pattern_edit.set_text("(")
    assert not edit.buttons[0].enabled and "unterminated" in edit.error.text
    edit.finish(0)  # 잘못된 채로 확인해도 저장되지 않는다
    assert bt.config.rules == []


def test_rules_dialog_edits_deletes_and_cancels(bt):
    bt.config.rules = ["cyan|^ok", "green|done"]
    bt._apply_rules()
    dialog = bt.open_rules_dialog()
    assert dialog.listing.items == ["cyan           ^ok", "green          done"]
    assert dialog.preview.rules[0].pattern.pattern == "^ok"

    dialog.listing.select(1)
    edit = bt.ask_rule(dialog.entries[1], lambda entry: dialog.entries.__setitem__(1, entry))
    edit.pattern_edit.set_text("finished")
    edit.finish(0)
    assert dialog.entries == ["cyan|^ok", "green|finished"]

    dialog.finish(1)  # 취소하면 설정은 그대로
    assert bt.config.rules == ["cyan|^ok", "green|done"]


def test_user_rules_come_before_the_defaults(bt):
    bt.config.rules = [r"magenta|\[OK\]"]
    bt._apply_rules()
    rules = bt.terminal.rules
    assert rules[0].pattern.pattern == r"\[OK\]" and len(rules) == 5
    bt.terminal.feed("[OK] boot\r\n")
    bt.app.step()
    assert "[OK] boot" in "\n".join(bt.app.screen_text())


def test_broken_entries_in_settings_are_skipped(tmp_path):
    path = tmp_path / "settings.json"
    term = make(config=Settings(rules=["nonsense", "pink|x", "red|(", "blue|ok"]), config_path=path)
    try:
        rules = user_rules(term)
        assert len(rules) == 1 and rules[0].pattern.pattern == "ok"
    finally:
        term.port.close()
        term.app.close()
