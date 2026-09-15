from retroui.input.events import CompositionEvent, Key, KeyEvent, Mod, TextEvent
from retroui.input.ime import ImeFilter
from retroui.input.mac_hotkeys import parse_hotkeys


def hotkeys(**entries):
    return {"AppleSymbolicHotKeys": entries}


def entry(params, enabled=True):
    return {"enabled": enabled, "value": {"parameters": params, "type": "standard"}}


SHIFT = 1 << 17
CTRL = 1 << 18
FN = 1 << 23


# ---- 설정 읽기 ----------------------------------------------------------


def test_reads_shift_space_as_configured_on_this_mac():
    # 실제 이 Mac 의 값: 60 = F18+fn (스페이스 아님), 61 = Shift+Space
    data = hotkeys(**{"60": entry([65535, 79, 8388608]), "61": entry([32, 49, SHIFT])})
    assert parse_hotkeys(data) == {Mod.SHIFT}


def test_default_ctrl_space_is_read_as_ctrl():
    assert parse_hotkeys(hotkeys(**{"60": entry([32, 49, CTRL])})) == {Mod.CTRL}


def test_disabled_shortcut_is_ignored():
    assert parse_hotkeys(hotkeys(**{"61": entry([32, 49, SHIFT], enabled=False)})) == set()


def test_shortcut_on_another_key_is_ignored():
    assert parse_hotkeys(hotkeys(**{"61": entry([65535, 79, SHIFT])})) == set()


def test_shortcut_with_a_modifier_sdl_cannot_report_is_ignored():
    """fn 은 SDL 이 알려주지 않는다: 섞인 채로 맞추면 Shift+Space 만 눌러도 버리게 된다."""
    assert parse_hotkeys(hotkeys(**{"61": entry([32, 49, SHIFT | FN])})) == set()


def test_missing_or_broken_settings_give_nothing():
    assert parse_hotkeys({}) == set()
    assert parse_hotkeys(hotkeys(**{"61": {"enabled": True}})) == set()


# ---- 필터 ----------------------------------------------------------------


def shift_space():
    return KeyEvent(Key.SPACE, Mod.SHIFT, "space")


def run(f, events):
    out = []
    for ev in events:
        out += f.feed(ev)
    return out


def test_recorded_switch_drops_the_key_and_its_space():
    """이 Mac 기록 그대로: Shift+Space KEYDOWN -> TEXTINPUT " " -> 다음 키부터 한글."""
    f = ImeFilter(space_switch_mods={Mod.SHIFT})
    out = run(f, [shift_space(), TextEvent(" "), TextEvent("ㅈ")])
    assert out == [TextEvent("ㅈ")]


def test_plain_space_is_kept():
    f = ImeFilter(space_switch_mods={Mod.SHIFT})
    ev = KeyEvent(Key.SPACE, Mod.NONE, "space")
    assert run(f, [ev, TextEvent(" ")]) == [ev, TextEvent(" ")]


def test_other_modifier_combination_is_kept():
    f = ImeFilter(space_switch_mods={Mod.SHIFT})
    ev = KeyEvent(Key.SPACE, Mod.SHIFT | Mod.CTRL, "space")
    assert run(f, [ev, TextEvent(" ")]) == [ev, TextEvent(" ")]


def test_without_the_shortcut_shift_space_types_a_space():
    """단축키를 설정하지 않은 사람이 Shift 를 누른 채 치는 스페이스는 그대로다."""
    f = ImeFilter()
    ev = shift_space()
    assert run(f, [ev, TextEvent(" ")]) == [ev, TextEvent(" ")]


def test_only_one_space_is_taken_from_a_commit_during_composition():
    f = ImeFilter(space_switch_mods={Mod.SHIFT})
    out = run(f, [CompositionEvent("한", 1), shift_space(), TextEvent("한 ")])
    assert TextEvent("한") in out
    assert TextEvent("한 ") not in out


def test_a_late_space_is_not_dropped():
    """전환 키 뒤 한참 지나 친 스페이스까지 버리면 안 된다."""
    now = [0.0]
    f = ImeFilter(clock=lambda: now[0], space_switch_mods={Mod.SHIFT})
    f.feed(shift_space())
    now[0] = 1.0
    assert f.feed(TextEvent(" ")) == [TextEvent(" ")]


def test_the_next_text_disarms_the_rule():
    f = ImeFilter(space_switch_mods={Mod.SHIFT})
    out = run(f, [shift_space(), TextEvent("a"), TextEvent(" ")])
    assert out == [TextEvent("a"), TextEvent(" ")]
