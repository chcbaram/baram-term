import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from retroui import App, Terminal, VBox  # noqa: E402
from retroui.input.events import IS_MAC, Key, KeyEvent, Mod, TextEvent, translate, us_ascii  # noqa: E402

SC_A, SC_1, SC_BACKSLASH, SC_PERIOD, SC_SPACE, SC_RETURN = 4, 30, 49, 55, 44, 40


def key(scancode, mod=Mod.NONE, caps=False, name=""):
    return KeyEvent(0, mod, name, scancode, caps)


# ---- 미국 배열 변환 ------------------------------------------------------


def test_letters_follow_shift_and_caps_lock():
    assert us_ascii(key(SC_A)) == "a"
    assert us_ascii(key(SC_A, Mod.SHIFT)) == "A"
    assert us_ascii(key(SC_A, caps=True)) == "A"
    assert us_ascii(key(SC_A, Mod.SHIFT, caps=True)) == "a"


def test_digits_and_symbols_follow_shift_only():
    assert us_ascii(key(SC_1)) == "1"
    assert us_ascii(key(SC_1, Mod.SHIFT)) == "!"
    assert us_ascii(key(SC_1, caps=True)) == "1"  # Caps Lock 은 숫자에 영향 없음
    assert us_ascii(key(SC_BACKSLASH)) == "\\"
    assert us_ascii(key(SC_BACKSLASH, Mod.SHIFT)) == "|"
    assert us_ascii(key(SC_PERIOD)) == "."
    assert us_ascii(key(SC_SPACE)) == " "


def test_non_character_keys_give_nothing():
    assert us_ascii(key(SC_RETURN)) is None
    assert us_ascii(key(0)) is None


def test_keydown_carries_scancode_and_caps_even_in_korean_mode():
    """한글 입력 상태에서는 키 이름이 비어서 온다 (녹화 기록). scancode 는 그대로 온다."""
    ev = pygame.event.Event(pygame.KEYDOWN, key=0, mod=pygame.KMOD_CAPS, scancode=26, unicode="ㅈ")
    out = translate(ev, 1.0, 8, 16)
    assert isinstance(out, KeyEvent)
    assert out.scancode == 26 and out.caps
    assert us_ascii(out) == "W"


# ---- 터미널 --------------------------------------------------------------


def make_term(ascii_input=True):
    term = Terminal()
    term.ascii_input = ascii_input
    sent = []
    term.send.connect(sent.append)
    return term, sent


def test_ascii_mode_turns_the_ime_off():
    term, _ = make_term()
    assert term.wants_text_input is False
    term.ascii_input = False
    assert term.wants_text_input is True


def test_ascii_mode_types_from_the_physical_key():
    term, sent = make_term()
    for ev in (key(SC_A), key(SC_A, Mod.SHIFT), key(SC_1, Mod.SHIFT), key(SC_SPACE)):
        assert term.on_event(ev)
    assert sent == [b"a", b"A", b"!", b" "]


def test_ctrl_letters_still_send_control_codes():
    term, sent = make_term()
    term.on_event(KeyEvent(Key.C, Mod.CTRL, "c", 6))
    assert sent == [b"\x03"]


def test_alt_combinations_are_not_turned_into_letters():
    term, sent = make_term()
    assert not term.on_event(key(SC_A, Mod.ALT))
    assert sent == []


def test_normal_mode_leaves_letters_to_the_ime():
    """옵션을 끄면 글자는 예전처럼 TEXTINPUT 으로만 온다 (KEYDOWN 에서 만들면 두 번 찍힌다)."""
    term, sent = make_term(ascii_input=False)
    assert not term.on_event(key(SC_A))
    term.on_event(TextEvent("가"))
    assert sent == ["가".encode()]


def test_refresh_text_input_applies_without_a_focus_change():
    try:
        app = App(title="t", size=(20, 6), headless=True)
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))
    try:
        term = Terminal()
        app.set_root(VBox(term))
        app.set_focus(term)
        assert app._text_input_active
        term.ascii_input = True
        assert app._text_input_active  # 포커스가 그대로라 아직 안 바뀐다
        app.refresh_text_input()
        assert not app._text_input_active
        term.ascii_input = False
        app.refresh_text_input()
        assert app._text_input_active
    finally:
        app.close()


@pytest.mark.skipif(not IS_MAC, reason="Cmd 조합은 macOS 에서만 앱으로 넘긴다")
def test_cmd_combinations_still_go_to_the_app_on_mac():
    term, sent = make_term()
    assert not term.on_event(key(SC_A, Mod.META))
    assert sent == []
