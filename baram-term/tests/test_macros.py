import time

import pytest
from retroui import ComboBox, Dialog, LineEdit
from retroui.input.events import Key, KeyEvent, Mod, MouseEvent

from baram_term import i18n
from baram_term.app import BaramTerm
from baram_term.macros import ADD_LABEL, MENU_KEY, SLOTS, USABLE_KEYS, free_keys, join_entry, join_macro, normalize, split_entry, split_macro
from baram_term.serial_port import PortSettings
from baram_term.settings import Settings


def test_split_uses_command_as_name_without_equals():
    assert split_macro("info") == ("info", "info")
    assert split_macro("부팅=boot 0") == ("부팅", "boot 0")
    assert split_macro("  이름  =  cmd  ") == ("이름", "cmd")


def test_split_empty_name_falls_back_to_command():
    assert split_macro("=reset") == ("reset", "reset")


def test_join_drops_redundant_name():
    assert join_macro("info", "info") == "info"
    assert join_macro("", "info") == "info"
    assert join_macro("부팅", "boot 0") == "부팅=boot 0"


def test_join_without_command_is_empty_slot():
    assert join_macro("이름만", "") == ""


def test_normalize_drops_blanks_and_clips_to_slot_count():
    assert normalize([" a ", "", "  ", "b"]) == ["F1|a", "F2|b"]
    assert len(normalize([str(i) for i in range(30)])) == SLOTS


def test_normalize_keeps_written_keys_and_sorts_by_them():
    assert normalize(["F7|plot", "F2|info"]) == ["F2|info", "F7|plot"]


def test_normalize_moves_a_duplicate_key_to_a_free_one():
    assert normalize(["F5|plot", "F5|info"]) == ["F1|info", "F5|plot"]


def test_split_and_join_round_trip_the_key():
    assert split_entry("F5|이름=명령") == (5, "이름", "명령")
    assert split_entry("info") == (None, "info", "info")
    assert join_entry(5, "이름", "명령") == "F5|이름=명령"
    assert join_entry(5, "", "info") == "F5|info"


def test_free_keys_skips_used_ones_but_keeps_the_edited_one():
    assert free_keys(["F1|a", "F3|b"])[:3] == [2, 4, 5]
    assert free_keys(["F1|a", "F3|b"], keep=3)[:3] == [2, 3, 4]


@pytest.fixture
def bt():
    i18n.set_language("en")
    try:
        term = BaramTerm(
            PortSettings(port="demo://"), headless=True, size=(100, 30),
            config=Settings(macro_bar=True, macros=["info", "리셋=reset"]),
        )
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))
    yield term
    term.port.close()
    term.app.close()


def pump(term, cond, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        term.app.step()
        if cond():
            return True
        time.sleep(0.01)
    return False


def screen(term):
    return "\n".join(term.app.screen_text())


def test_bar_shows_registered_macros_then_the_add_button(bt):
    bt.app.ensure_layout()
    assert [b.text for b in bt.macro_bar.buttons] == ["F1 info", "F2 리셋", ADD]


def test_function_key_sends_the_command(bt):
    bt.connect()
    assert pump(bt, lambda: "cli#" in screen(bt))
    bt.app.dispatch(KeyEvent(Key.F1, Mod.NONE, "f1"))
    assert pump(bt, lambda: "Board" in screen(bt))


def test_key_with_no_macro_is_not_swallowed(bt):
    assert bt._macro_slot(Key.F3) == 3
    assert bt.macro_bar.index_of_key(3) is None
    assert not bt._key_filter(KeyEvent(Key.F3, Mod.NONE, "f3"))


def test_f10_stays_the_menu_key(bt):
    assert bt.MACRO_KEYS[9] is None
    assert bt._macro_slot(Key.F10) is None


def test_adding_from_the_plus_button_appends(bt):
    bt._set_macro(2, join_entry(3, "플롯", "plot"))
    assert bt.macro_bar.macros == ["F1|info", "F2|리셋=reset", "F3|플롯=plot"]
    assert [b.text for b in bt.macro_bar.buttons] == ["F1 info", "F2 리셋", "F3 플롯", ADD]


def test_deleting_keeps_the_other_keys_where_they_were(bt):
    bt._set_macro(0, "")
    assert bt.macro_bar.macros == ["F2|리셋=reset"]
    assert [b.text for b in bt.macro_bar.buttons] == ["F2 리셋", ADD]


def test_a_full_bar_has_no_add_button(bt):
    bt.macro_bar.set_macros([f"cmd{i}" for i in range(SLOTS)])
    assert len(bt.macro_bar.buttons) == SLOTS
    assert bt.macro_bar.buttons[-1].text.startswith(f"F{USABLE_KEYS[-1]}")


def test_f10_is_not_offered_as_a_macro_key(bt):
    """F10 은 메뉴바 키라 눌러도 매크로가 안 나간다. 고를 수도 없어야 한다."""
    assert MENU_KEY not in USABLE_KEYS
    dialog = bt.ask_macro(len(bt.macro_bar.macros))
    combo = next(w for w in dialog.iter_tree() if isinstance(w, ComboBox))
    assert "F10" not in combo.items


def test_f10_written_by_hand_is_moved_to_a_free_key():
    assert normalize(["F10|plot", "F1|help"]) == ["F1|help", "F2|plot"]


def test_toggle_hides_the_bar_and_is_saved(bt):
    bt._apply_macro_bar(False)
    assert not bt.macro_bar.visible and not bt.config.macro_bar
    bt._apply_macro_bar(True)
    assert bt.macro_bar.visible and bt.config.macro_bar


def test_macros_are_written_to_settings(bt):
    bt._set_macro(2, join_entry(3, "", "status"))
    assert bt.config.macros == ["F1|info", "F2|리셋=reset", "F3|status"]


def make(cols, macros):
    i18n.set_language("en")
    try:
        term = BaramTerm(
            PortSettings(port="demo://"), headless=True, size=(cols, 20),
            config=Settings(macro_bar=True, macros=macros),
        )
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))
    term.app.ensure_layout()
    return term


def test_narrow_window_shortens_names_before_hiding_anything():
    """좁아지면 숨기지 말고 이름부터 줄여서 모든 칸을 보여준다."""
    macros = ["help", "info", "reset", "status", "sensor"]
    term = make(40, macros)
    try:
        assert all(b.rect.w for b in term.macro_bar.buttons), "모든 칸이 자리를 받아야 한다"
        assert not term.macro_bar.more.text, "숨긴 칸이 없으니 +N 도 없다"
        assert [b.text for b in term.macro_bar.buttons] == [f"F{i}" for i in range(1, 6)] + ["+"]  # 좁아서 설명은 빠진다
        assert term.macro_bar.buttons[-1].rect.right <= term.macro_bar.rect.right
    finally:
        term.port.close()
        term.app.close()


def test_wide_window_keeps_full_names():
    term = make(100, ["help", "info", "reset"])
    try:
        assert [b.text for b in term.macro_bar.buttons] == ["F1 help", "F2 info", "F3 reset", ADD]
    finally:
        term.port.close()
        term.app.close()


def test_names_are_dropped_rather_than_cut_to_a_stub():
    """`F1 he…` 처럼 두 글자 + 말줄임은 자리만 먹으니, 그럴 바엔 번호만 남긴다."""
    term = make(52, ["help", "info", "reset", "status", "sensor", "log"])
    try:
        assert all("…" not in b.text for b in term.macro_bar.buttons)
    finally:
        term.port.close()
        term.app.close()


def test_hidden_slots_are_counted_when_even_numbers_do_not_fit():
    term = make(30, [f"cmd{i}" for i in range(10)])
    try:
        hidden = sum(1 for b in term.macro_bar.buttons if not b.rect.w)
        assert hidden and term.macro_bar.more.text == f"+{hidden}"
    finally:
        term.port.close()
        term.app.close()


def test_slot_wider_than_the_bar_is_still_drawn():
    """한 칸이 막대보다 길어도 사라지지 않고 줄여서 그린다 (F 키가 있는데 버튼만 없으면 헷갈린다)."""
    term = make(8, ["a" * 60])
    try:
        first = term.macro_bar.buttons[0]
        assert first.rect.w > 0
        assert first.rect.right <= term.macro_bar.rect.right
    finally:
        term.port.close()
        term.app.close()


def test_button_tooltip_carries_the_full_command():
    i18n.set_language("en")
    long_cmd = "nvs set wifi_ssid_long_name_here 1234567890"
    try:
        term = BaramTerm(
            PortSettings(port="demo://"), headless=True, size=(80, 20),
            config=Settings(macro_bar=True, macros=[long_cmd]),
        )
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))
    try:
        assert term.macro_bar.buttons[0].tooltip == long_cmd
        assert term.macro_bar.buttons[1].tooltip  # 빈 칸도 안내가 있다
    finally:
        term.port.close()
        term.app.close()


ADD = f"{ADD_LABEL} Add Macro"  # [+] 버튼은 자리가 되면 설명을 함께 보여준다


def right_click(term, button):
    ev = MouseEvent("down", 3, button.rect.x + 1, button.rect.y, 0, 0, Mod.NONE)
    return term.macro_bar.on_event(ev)


def test_right_click_on_a_filled_slot_opens_the_menu(bt):
    bt.app.ensure_layout()
    assert right_click(bt, bt.macro_bar.buttons[0])
    popup = bt.app.popups[-1]
    assert popup.items == ["Edit", "Delete"]


def test_menu_edit_opens_the_dialog(bt):
    bt.app.ensure_layout()
    right_click(bt, bt.macro_bar.buttons[0])
    bt.app.popups[-1].on_choose(0)
    assert any(isinstance(p, Dialog) for p in bt.app.popups)


def test_menu_delete_removes_the_macro(bt):
    bt.app.ensure_layout()
    right_click(bt, bt.macro_bar.buttons[1])
    bt.app.popups[-1].on_choose(1)
    assert bt.macro_bar.macros == ["F1|info"]


def test_right_click_on_the_add_button_goes_straight_to_the_dialog(bt):
    bt.app.ensure_layout()
    add = bt.macro_bar.buttons[-1]
    assert add.text.startswith("+")
    assert right_click(bt, add)
    assert any(isinstance(p, Dialog) for p in bt.app.popups)


def test_the_add_dialog_has_no_delete_button(bt):
    dialog = bt.ask_macro(len(bt.macro_bar.macros))
    assert len(dialog.buttons) == 2


def test_left_click_still_sends(bt):
    sent = []
    bt.send = lambda data, raw=False: sent.append(data)
    bt.macro_bar.buttons[0].click()
    assert sent and b"info" in sent[0]


def test_long_name_is_shortened_on_the_button():
    long_name = "nvs set wifi_ssid_long_name_here 1234567890"
    term = make(100, [long_name])
    try:
        assert term.macro_bar.buttons[0].text == "F1 nvs set wifi_…"
        assert split_entry(term.macro_bar.macros[0])[2] == long_name  # 보내는 명령은 그대로
    finally:
        term.port.close()
        term.app.close()


def test_dialog_inputs_line_up_in_every_language():
    """라벨 길이가 언어마다 달라도(en: Command/Name) 입력칸은 같은 열에서 시작한다."""
    for lang in ("ko", "en"):
        i18n.set_language(lang)
        term = make(90, ["wifi=nvs set x"])
        try:
            dialog = term.ask_macro(0)
            term.app.step()
            edits = [w for w in dialog.iter_tree() if isinstance(w, LineEdit)]
            assert len(edits) == 2
            assert edits[0].rect.x == edits[1].rect.x, lang
            assert edits[0].rect.w == edits[1].rect.w, lang
        finally:
            term.port.close()
            term.app.close()


def test_right_click_menu_does_not_overlap_a_tooltip(bt):
    """툴팁이 떠 있는 채로 오른쪽 클릭하면 메뉴만 남아야 한다 (겹쳐 보였다)."""
    bt.app.ensure_layout()
    bt.app.tooltip_delay = 0.05
    button = bt.macro_bar.buttons[0]
    bt.app.dispatch(MouseEvent("move", 0, button.rect.x + 1, button.rect.y, 0, 0, Mod.NONE))
    end = time.monotonic() + 0.3
    while time.monotonic() < end:
        bt.app.step()
        time.sleep(0.01)
    assert bt.app.popups, "먼저 툴팁이 떠 있어야 하는 상황"
    bt.app.dispatch(MouseEvent("down", 3, button.rect.x + 1, button.rect.y, 0, 0, Mod.NONE))
    end = time.monotonic() + 0.3
    while time.monotonic() < end:
        bt.app.step()
        time.sleep(0.01)
    assert [type(p).__name__ for p in bt.app.popups] == ["ListPopup"]


def test_key_picker_offers_only_free_keys(bt):
    """이미 쓰는 번호는 고를 목록에서 뺀다 (F1, F2 를 쓰는 중)."""
    dialog = bt.ask_macro(len(bt.macro_bar.macros))
    combo = next(w for w in dialog.iter_tree() if isinstance(w, ComboBox))
    assert combo.items[0] == "F3"
    assert "F1" not in combo.items and "F2" not in combo.items


def test_key_picker_keeps_the_key_being_edited(bt):
    dialog = bt.ask_macro(0)  # F1 을 고치는 중
    combo = next(w for w in dialog.iter_tree() if isinstance(w, ComboBox))
    assert combo.items[0] == "F1" and combo.index == 0
    assert "F2" not in combo.items  # 다른 매크로가 쓰는 번호는 여전히 뺀다


def test_chosen_key_decides_the_function_key(bt):
    bt._set_macro(len(bt.macro_bar.macros), join_entry(9, "", "status"))
    assert bt.macro_bar.index_of_key(9) == 2
    sent = []
    bt.send = lambda data, raw=False: sent.append(data)
    assert bt._key_filter(KeyEvent(Key.F9, Mod.NONE, "f9"))
    assert sent and b"status" in sent[0]


def test_add_button_drops_its_label_when_space_runs_out():
    """좁아지면 설명을 떼고 `+` 만 남긴다 (매크로 칸이 먼저다)."""
    term = make(34, ["F1|help", "F3|info", "F5|reset"])
    try:
        assert term.macro_bar.buttons[-1].text == ADD_LABEL
    finally:
        term.port.close()
        term.app.close()


def test_empty_bar_shows_only_the_add_button():
    term = make(90, [])
    try:
        assert [b.text for b in term.macro_bar.buttons] == [ADD]
    finally:
        term.port.close()
        term.app.close()


def test_ascii_input_is_on_by_default():
    assert Settings().ascii_input is True


def test_ascii_input_option_toggles_the_terminal_ime(bt):
    """보기 메뉴의 영문 입력 옵션 (기본 켜짐): 터미널 IME 를 바로 끄고 켜며, 설정에 남긴다."""
    bt.app.set_focus(bt.terminal)
    assert bt.terminal.ascii_input and bt.item_ascii.checked
    assert not bt.app._text_input_active  # 기본: 영문 입력이라 IME 꺼짐
    bt._apply_ascii_input(False)
    assert not bt.terminal.ascii_input and not bt.item_ascii.checked and not bt.config.ascii_input
    assert bt.app._text_input_active
    bt._apply_ascii_input(True)
    assert bt.config.ascii_input and not bt.app._text_input_active
