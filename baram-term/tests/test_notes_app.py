import pytest
from retroui import Dialog, FileDialog, ListPopup
from retroui.input.events import TextEvent

from baram_term import i18n
from baram_term import notes as notes_store
from baram_term import settings as store
from baram_term.app import BaramTerm
from baram_term.notes import MAX_NOTES, Note
from baram_term.serial_port import PortSettings
from baram_term.settings import Settings


def make(tmp_path, config=None):
    i18n.set_language("en")
    try:
        return BaramTerm(
            PortSettings(port="demo://"),
            headless=True,
            size=(120, 36),
            config=config or Settings(),
            config_path=tmp_path / "settings.json",
        )
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))


@pytest.fixture
def bt(tmp_path):
    term = make(tmp_path)
    term._apply_hex(True)
    term.app.step()
    yield term
    term.port.close()
    term.app.close()


def add_note(term, title, text=""):
    dialog = term.add_note()
    dialog.edit.set_text(title)
    dialog.finish(0)
    if text:
        term.note_area.set_text(text)
    return term.notes[-1]


def test_tabs_start_with_hex_and_add_memo_pages(bt):
    assert bt.right_tabs.titles == ["HEX"] and bt.hex_page.visible and not bt.note_page.visible

    add_note(bt, "boot", "reset\nlog on")
    assert bt.right_tabs.titles == ["HEX", "boot"] and bt.right_tabs.selected == 1
    assert bt.note_page.visible and not bt.hex_page.visible
    assert bt.notes[0].text == "reset\nlog on"
    bt.app.step()
    assert "reset" in "\n".join(bt.app.screen_text())

    bt.right_tabs.select(0)
    assert bt.hex_page.visible and not bt.note_page.visible and bt.hex_active


def test_memo_text_is_saved_and_restored(tmp_path):
    term = make(tmp_path)
    try:
        term._apply_hex(True)
        add_note(term, "boot", "reset")
        term._save_notes()
    finally:
        term.port.close()
        term.app.close()
    assert (tmp_path / "notes.json").exists()
    saved = store.load(tmp_path / "settings.json")[0]
    assert saved.right_tab == 1

    again = make(tmp_path, config=saved)
    try:
        assert [n.title for n in again.notes] == ["boot"] and again.notes[0].text == "reset"
        assert again.right_tabs.selected == 1 and again.note_area.text == "reset"
    finally:
        again.port.close()
        again.app.close()


def test_titles_are_unique_and_capped(bt):
    add_note(bt, "boot")
    add_note(bt, "boot")
    assert [n.title for n in bt.notes] == ["boot", "boot (2)"]

    while len(bt.notes) < MAX_NOTES:
        add_note(bt, f"memo{len(bt.notes)}")
    assert bt.add_note() is None  # 더는 못 만든다
    assert "at most" in "\n".join(bt.app.screen_text())


def test_tab_menu_renames_and_deletes(bt):
    add_note(bt, "boot", "reset")
    add_note(bt, "sensor", "start")

    assert bt.open_note_menu(0, 0, 0) is None  # HEX 탭에는 메모 메뉴가 없다
    popup = bt.open_note_menu(1, 0, 0)  # 첫 메모 탭
    assert isinstance(popup, ListPopup) and popup.items[:3] == ["Rename", "Export...", "Delete"]
    popup.choose(0)
    rename = bt.app.popups[-1]
    rename.edit.set_text("boot steps")
    rename.finish(0)
    assert bt.notes[0].title == "boot steps" and bt.right_tabs.titles == ["HEX", "boot steps", "sensor"]

    bt.delete_note(0)
    assert [n.title for n in bt.notes] == ["sensor"] and bt.right_tabs.titles == ["HEX", "sensor"]


def test_export_and_import_through_file_dialogs(bt, tmp_path):
    add_note(bt, "boot", "reset\nlog on")
    dialog = bt.export_note(0)
    assert isinstance(dialog, FileDialog)
    dialog.name_edit.set_text(str(tmp_path / "boot.txt"))
    dialog.finish(0)
    assert (tmp_path / "boot.txt").read_text() == "reset\nlog on\n"
    assert "memo saved" in "\n".join(bt.app.screen_text())

    bt.delete_note(0)
    assert bt.notes == []
    opened = bt.import_notes()
    opened.name_edit.set_text(str(tmp_path / "boot.txt"))
    opened.finish(0)
    assert [n.title for n in bt.notes] == ["boot"] and bt.notes[0].text == "reset\nlog on"
    assert "imported 1" in "\n".join(bt.app.screen_text())


def test_import_json_keeps_titles_unique(bt, tmp_path):
    add_note(bt, "boot", "one")
    path = tmp_path / "all.json"
    notes_store.export_all([Note("boot", "x"), Note("extra", "y")], path)
    opened = bt.import_notes()
    opened.name_edit.set_text(str(path))
    opened.finish(0)
    assert [n.title for n in bt.notes] == ["boot", "boot (2)", "extra"]


def test_hex_collects_only_on_its_tab(bt):
    add_note(bt, "boot")
    assert not bt.hex_active
    bt.hex_view.clear()
    bt._on_rx()  # 메모 탭에서는 HEX 에 쌓지 않는다
    assert bt.hex_view.rows == []
    bt.right_tabs.select(0)
    assert bt.hex_active


def test_menu_picks_hex_or_memo_and_toggles_off(bt):
    bt._apply_hex(False)
    assert not bt.right_frame.visible and not bt.item_hex.checked and not bt.item_memo.checked

    bt._show_right_tab(0)  # 보기 메뉴 > HEX 보기
    assert bt.right_frame.visible and bt.right_tabs.selected == 0
    assert bt.item_hex.checked and not bt.item_memo.checked

    bt._show_right_tab(0)  # 같은 것을 다시 고르면 닫는다
    assert not bt.right_frame.visible and not bt.item_hex.checked

    dialog = bt._show_right_tab(1) or bt.app.popups[-1]  # 메모가 없으면 먼저 만든다
    dialog.edit.set_text("boot")
    dialog.finish(0)
    assert bt.right_frame.visible and bt.right_tabs.selected == 1
    assert bt.item_memo.checked and not bt.item_hex.checked

    bt.right_tabs.select(0)  # 탭을 직접 눌러도 메뉴 표시가 따라간다
    assert bt.item_hex.checked and not bt.item_memo.checked


def test_panel_state_and_menu_checks_survive_a_restart(tmp_path):
    term = make(tmp_path)
    try:
        dialog = term.add_note()  # + 로 메모를 만들면 패널이 열린다
        dialog.edit.set_text("boot")
        dialog.finish(0)
        term.note_area.set_text("test")
        term._save_notes()
        assert term.right_frame.visible and term.item_memo.checked
    finally:
        term.port.close()
        term.app.close()

    saved = store.load(tmp_path / "settings.json")[0]
    assert saved.hex is True and saved.right_tab == 1  # 패널이 열렸다는 것도 저장된다

    again = make(tmp_path, config=saved)
    try:
        assert again.right_frame.visible and again.right_tabs.selected == 1
        assert again.item_memo.checked and not again.item_hex.checked  # 메뉴 체크도 그대로
    finally:
        again.port.close()
        again.app.close()
