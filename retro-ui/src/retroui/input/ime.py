"""IME event correction for Korean input.

macOS SDL2 두벌식 실측 (tests/fixtures/ime_macos_2set.json) 에서 확인한 문제를 보정한다.

1. 조합 중 편집키: Enter/Tab/화살표 등의 KEYDOWN 이 조합 확정 TEXTINPUT 보다 먼저 온다.
   그대로 처리하면 Enter 동작이 마지막 글자를 빠뜨린다.
   -> KEYDOWN 전에 조합 중 글자를 직접 확정하고, 뒤따라오는 같은 문자열 확정/조합 반복은 버린다.
2. 조합 중 Backspace: 자모를 지우지 않고 조합 중 글자를 그대로 확정해 버린다.
   -> 확정을 버리고 마지막 자모만 뺀 글자를 넣는다 ("한" -> "하", "ㅗ" -> "").
3. 조합 중 스페이스/마침표 같은 글자 키는 IME 가 "철 " 처럼 붙여서 확정하므로 건드리지 않는다.

TEXTINPUT 이 KEYDOWN 보다 먼저 오는 플랫폼에서는 KEYDOWN 시점에 조합이 비어 있어 아무것도 하지 않는다.
"""

from __future__ import annotations

import time
from typing import Callable

from retroui.input.events import CompositionEvent, Event, Key, KeyEvent, Mod, TextEvent

_EDIT_KEYS = {
    Key.RETURN, Key.KP_ENTER, Key.BACKSPACE, Key.DELETE, Key.TAB, Key.ESCAPE,
    Key.LEFT, Key.RIGHT, Key.UP, Key.DOWN, Key.HOME, Key.END, Key.PAGEUP, Key.PAGEDOWN,
}

# 뒤늦게 오는 중복 확정을 기다리는 시간. macOS 는 같은 이벤트 묶음으로 바로 보낸다
_SUPPRESS_S = 0.3

_CHOSEONG_COMPAT = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
# 겹받침 -> 앞 받침 (종성 인덱스)
_FINAL_REDUCE = {3: 1, 5: 4, 6: 4, 9: 8, 10: 8, 11: 8, 12: 8, 13: 8, 14: 8, 15: 8, 18: 17}
# 겹모음 -> 앞 모음 (중성 인덱스)
_VOWEL_REDUCE = {9: 8, 10: 8, 11: 8, 14: 13, 15: 13, 16: 13, 19: 18}


def hangul_backspace(text: str) -> str:
    """마지막 글자에서 자모 하나를 뺀다. 한글 음절이 아니면 글자를 지운다."""
    if not text:
        return text
    code = ord(text[-1])
    if not 0xAC00 <= code <= 0xD7A3:
        return text[:-1]
    idx = code - 0xAC00
    lead, vowel, final = idx // 588, (idx % 588) // 28, idx % 28
    if final:
        return text[:-1] + chr(0xAC00 + (lead * 21 + vowel) * 28 + _FINAL_REDUCE.get(final, 0))
    if vowel in _VOWEL_REDUCE:
        return text[:-1] + chr(0xAC00 + (lead * 21 + _VOWEL_REDUCE[vowel]) * 28)
    return text[:-1] + _CHOSEONG_COMPAT[lead]


class ImeFilter:
    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self.clock = clock
        self.preedit = ""
        self._suppress: str | None = None
        self._suppress_until = 0.0

    def _arm(self, text: str) -> None:
        self._suppress = text
        self._suppress_until = self.clock() + _SUPPRESS_S

    def commit_pending(self) -> str:
        """조합 중 글자를 넘겨받아 직접 확정할 때 쓴다. 이후 IME 가 보내는 같은 확정은 버린다."""
        pending = self.preedit
        self.preedit = ""
        if pending:
            self._arm(pending)
        return pending

    def feed(self, ev: Event) -> list[Event]:
        if self._suppress is not None and self.clock() > self._suppress_until:
            self._suppress = None

        if isinstance(ev, CompositionEvent):
            if self._suppress is not None and ev.text == self._suppress:
                return []
            self.preedit = ev.text
            return [ev]

        if isinstance(ev, TextEvent):
            if self._suppress is not None:
                expected = self._suppress
                self._suppress = None
                if ev.text == expected:
                    return []
            self.preedit = ""
            return [ev]

        if isinstance(ev, KeyEvent) and self.preedit and (ev.key in _EDIT_KEYS or ev.mod & (Mod.CTRL | Mod.META)):
            pending = self.commit_pending()
            if ev.key == Key.BACKSPACE and not ev.mod:
                reduced = hangul_backspace(pending)
                out: list[Event] = [CompositionEvent("", 0)]
                if reduced:
                    out.append(TextEvent(reduced))
                return out
            return [TextEvent(pending), CompositionEvent("", 0), ev]

        return [ev]
