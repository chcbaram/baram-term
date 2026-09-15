import json
import pathlib

import pygame
import pytest

from retroui import App, LineEdit, VBox
from retroui.input.events import CompositionEvent, Key, KeyEvent, Mod, TextEvent, mod_from_pygame, normalize_key
from retroui.input.ime import ImeFilter, hangul_backspace

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "ime_macos_2set.json"


@pytest.mark.parametrize(
    "before, after",
    [("한", "하"), ("하", "ㅎ"), ("ㅎ", ""), ("닭", "달"), ("과", "고"), ("의", "으"), ("안녕", "안녀"), ("ab", "a"), ("", "")],
)
def test_hangul_backspace(before, after):
    assert hangul_backspace(before) == after


def test_enter_during_composition_commits_before_the_key():
    f = ImeFilter()
    assert f.feed(CompositionEvent("트", 1)) == [CompositionEvent("트", 1)]
    enter = KeyEvent(Key.RETURN, Mod.NONE, "return")
    assert f.feed(enter) == [TextEvent("트"), CompositionEvent("", 0), enter]
    # macOS 가 뒤이어 보내는 조합 반복과 중복 확정은 버린다
    assert f.feed(CompositionEvent("트", 1)) == []
    assert f.feed(CompositionEvent("", 0)) == [CompositionEvent("", 0)]
    assert f.feed(TextEvent("트")) == []
    assert f.feed(TextEvent("트")) == [TextEvent("트")]  # 억제는 한 번만


def test_backspace_during_composition_removes_last_jamo():
    f = ImeFilter()
    f.feed(CompositionEvent("한", 1))
    assert f.feed(KeyEvent(Key.BACKSPACE, Mod.NONE, "backspace")) == [CompositionEvent("", 0), TextEvent("하")]
    assert f.feed(TextEvent("한")) == []


def test_printable_key_during_composition_passes_through():
    f = ImeFilter()
    f.feed(CompositionEvent("철", 1))
    space = KeyEvent(pygame.K_SPACE, Mod.NONE, "space")
    assert f.feed(space) == [space]
    assert f.feed(TextEvent("철 ")) == [TextEvent("철 ")]


def test_suppression_expires():
    now = [0.0]
    f = ImeFilter(clock=lambda: now[0])
    f.feed(CompositionEvent("가", 1))
    f.feed(KeyEvent(Key.RETURN, Mod.NONE, "return"))
    now[0] = 1.0
    assert f.feed(TextEvent("가")) == [TextEvent("가")]


def test_normalize_key_restores_latin_keys_from_scancode():
    assert normalize_key(0, "", 4) == (pygame.K_a, "a")
    assert normalize_key(0, "", 29) == (pygame.K_z, "z")
    assert normalize_key(0, "", 30) == (pygame.K_1, "1")
    assert normalize_key(0, "", 39) == (pygame.K_0, "0")
    assert normalize_key(pygame.K_RETURN, "return", 40) == (pygame.K_RETURN, "return")


@pytest.fixture
def app():
    try:
        a = App(headless=True, size=(40, 5))
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))
    yield a
    a.close()


def recorded_events():
    for e in json.loads(FIXTURE.read_text(encoding="utf-8")):
        t = e["type"]
        if t == "KEYDOWN":
            name = e["key"]
            key = pygame.key.key_code(name) if name else 0
            key, name = normalize_key(key, name, e["scancode"])
            yield KeyEvent(key, mod_from_pygame(e["mod"]), name)
        elif t == "TEXTEDITING":
            yield CompositionEvent(e["text"], e["start"])
        elif t == "TEXTINPUT":
            yield TextEvent(e["text"])


def test_replay_recorded_macos_session_into_line_edit(app):
    """실제 macOS 두벌식 입력 기록 재생.

    기록 내용: f, Backspace, 입력기 전환, ㅈ(바로 확정), ㅗ 조합 중 Backspace, Backspace x3,
    '조한철 이렇게 합니다. ' Enter, '이것은 테스트' (트 조합 중) Enter.
    """
    sent = []
    edit = LineEdit(clear_on_submit=True, on_submit=sent.append)
    app.set_root(VBox(edit))
    app.step()
    for ev in recorded_events():
        app.dispatch(ev)
    assert sent == ["조한철 이렇게 합니다. ", "이것은 테스트"]
    assert edit.text == "" and edit.preedit == ""
