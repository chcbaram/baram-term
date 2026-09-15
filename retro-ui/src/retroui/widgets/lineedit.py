"""Single-line text input with Korean IME support.

확정 글자는 TextEvent 로만 넣고, 조합 중 글자(preedit)는 텍스트 모델에 넣지 않고 캐럿 위치에
밑줄로만 그린다. KEYDOWN 의 글자 키는 무시한다 (IME 가 TEXTINPUT 으로 보낸다).
"""

from __future__ import annotations

from typing import Callable

from retroui.core.geometry import Rect
from retroui.core.signal import Signal
from retroui.core.wcwidth import char_width, normalize, str_width, truncate
from retroui.input.events import CompositionEvent, Event, FocusEvent, Key, KeyEvent, Mod, MouseEvent, TextEvent
from retroui.render.cellbuffer import Attr
from retroui.render.painter import Painter
from retroui.widgets.base import SizeHint, Widget

_local_clipboard = ""


def clipboard_get() -> str:
    try:
        import pygame

        text = pygame.scrap.get_text()
        if text:
            return text
    except Exception:
        pass
    return _local_clipboard


def clipboard_put(text: str) -> None:
    global _local_clipboard
    _local_clipboard = text
    try:
        import pygame

        pygame.scrap.put_text(text)
    except Exception:
        pass


class LineEdit(Widget):
    focusable = True
    wants_text_input = True

    def __init__(
        self,
        text: str = "",
        *,
        placeholder: str = "",
        max_length: int | None = None,
        validator: Callable[[str], bool] | None = None,
        clear_on_submit: bool = False,
        history: bool = False,
        on_submit: Callable[[str], None] | None = None,
        on_change: Callable[[str], None] | None = None,
        stretch: int = 1,
        **kw,
    ):
        super().__init__(stretch=stretch, **kw)
        self.placeholder = placeholder
        self.max_length = max_length
        self.validator = validator
        self.clear_on_submit = clear_on_submit
        self.changed = Signal()
        self.submitted = Signal()
        if on_submit is not None:
            self.submitted.connect(on_submit)
        if on_change is not None:
            self.changed.connect(on_change)
        self.history_enabled = history
        self.history: list[str] = []
        self._history_pos: int | None = None
        self.text = normalize(str(text))
        self.cursor = len(self.text)
        self.anchor: int | None = None
        self.preedit = ""
        self.scroll = 0
        self._dragging = False

    # ---- model ---------------------------------------------------------

    def set_text(self, text: str, emit: bool = True) -> None:
        text = normalize(str(text))
        if self.max_length is not None:
            text = text[: self.max_length]
        changed = text != self.text
        self.text = text
        self.cursor = len(text)
        self.anchor = None
        self.preedit = ""
        self.invalidate()
        if changed and emit:
            self.changed.emit(text)

    def selection(self) -> tuple[int, int] | None:
        if self.anchor is None or self.anchor == self.cursor:
            return None
        return min(self.anchor, self.cursor), max(self.anchor, self.cursor)

    def selected_text(self) -> str:
        sel = self.selection()
        return self.text[sel[0] : sel[1]] if sel else ""

    def _replace(self, start: int, end: int, s: str) -> bool:
        if self.max_length is not None:
            room = self.max_length - (len(self.text) - (end - start))
            s = s[: max(0, room)]
        new = self.text[:start] + s + self.text[end:]
        if self.validator is not None and not self.validator(new):
            return False
        self.text = new
        self.cursor = start + len(s)
        self.anchor = None
        self.invalidate()
        self.changed.emit(new)
        return True

    def insert(self, s: str) -> bool:
        # 한 줄 입력: 제어 문자(줄바꿈 포함)는 버린다
        s = "".join(ch for ch in normalize(s) if ch >= " " and ch != "\x7f")
        start, end = self.selection() or (self.cursor, self.cursor)
        return self._replace(start, end, s)

    def backspace(self) -> None:
        sel = self.selection()
        if sel:
            self._replace(sel[0], sel[1], "")
        elif self.cursor > 0:
            self._replace(self.cursor - 1, self.cursor, "")

    def delete(self) -> None:
        sel = self.selection()
        if sel:
            self._replace(sel[0], sel[1], "")
        elif self.cursor < len(self.text):
            self._replace(self.cursor, self.cursor + 1, "")

    def move(self, pos: int, extend: bool = False) -> None:
        pos = max(0, min(pos, len(self.text)))
        if extend:
            if self.anchor is None:
                self.anchor = self.cursor
        else:
            self.anchor = None
        self.cursor = pos
        self.invalidate()

    def select_all(self) -> None:
        self.anchor = 0
        self.cursor = len(self.text)
        self.invalidate()

    # ---- geometry ------------------------------------------------------

    @property
    def caret_col(self) -> int:
        return str_width(self.text[: self.cursor] + self.preedit)

    def caret_cell(self) -> tuple[int, int] | None:
        if not self.focused or self.rect.w <= 0:
            return None
        x = max(0, min(self.caret_col - self.scroll, self.rect.w - 1))
        return self.rect.x + x, self.rect.y

    def index_at(self, cx: int) -> int:
        """셀 열 위치를 글자 인덱스로. 와이드 문자의 오른쪽 절반을 누르면 그 글자 뒤."""
        target = cx - self.rect.x + self.scroll
        col = 0
        for i, ch in enumerate(self.text):
            w = char_width(ch)
            if target < col + max(1, w) / 2:
                return i
            col += w
        return len(self.text)

    def _scroll_to_caret(self, display: str) -> None:
        w = self.rect.w
        caret = self.caret_col
        after = self.cursor + len(self.preedit)
        caret_w = char_width(display[after]) if after < len(display) else 1
        if str_width(display) + 1 <= w:
            self.scroll = 0
        elif caret < self.scroll:
            self.scroll = caret
        elif caret + caret_w > self.scroll + w:
            self.scroll = caret + caret_w - w

    def size_hint(self) -> SizeHint:
        w = max(10, str_width(self.text) + 2, str_width(self.placeholder) + 2)
        return SizeHint(4, 1, w, 1, max_h=1)

    # ---- paint ---------------------------------------------------------

    def paint(self, p: Painter) -> None:
        pal = self.palette
        w = self.rect.w
        focused = self.focused
        fg = pal.input_fg if self.enabled else pal.disabled
        bg = pal.input_bg
        p.fill(Rect(0, 0, w, self.rect.h), " ", fg, bg)
        if w <= 0:
            return

        if not self.text and not self.preedit:
            self.scroll = 0
            if self.placeholder:
                p.text(0, 0, truncate(self.placeholder, w), pal.dim, bg)
            if focused:
                first = self.placeholder[:1] or " "
                p.put(0, 0, first, pal.dim if self.placeholder else fg, bg, Attr.REVERSE)
            return

        display = self.text[: self.cursor] + self.preedit + self.text[self.cursor :]
        pre_start, pre_end = self.cursor, self.cursor + len(self.preedit)
        self._scroll_to_caret(display)
        sel = self.selection()

        col = 0
        for i, ch in enumerate(display):
            cw = char_width(ch)
            if cw == 0:
                continue
            x = col - self.scroll
            col += cw
            if x < 0:
                continue  # 왼쪽으로 스크롤돼 나간 글자 (경계에 걸친 와이드 문자 포함)
            if x >= w:
                break
            cfg, cbg, attr = fg, bg, 0
            if pre_start <= i < pre_end:
                cfg, attr = pal.accent, Attr.UNDERLINE
            else:
                ti = i if i < pre_start else i - len(self.preedit)
                if sel and sel[0] <= ti < sel[1]:
                    cfg, cbg = pal.sel_fg, pal.sel_bg
            if focused and i == pre_end:
                attr |= Attr.REVERSE
            p.put(x, 0, ch, cfg, cbg, attr)

        if focused and pre_end >= len(display):
            x = self.caret_col - self.scroll
            if 0 <= x < w:
                p.put(x, 0, " ", fg, bg, Attr.REVERSE)

    # ---- events --------------------------------------------------------

    def _submit(self) -> bool:
        if not len(self.submitted) and not self.clear_on_submit:
            return False  # 받을 곳이 없으면 부모(대화상자 기본 버튼 등)로 넘긴다
        text = self.text
        if self.history_enabled and text and (not self.history or self.history[-1] != text):
            self.history.append(text)
        self._history_pos = None
        if self.clear_on_submit:
            self.set_text("")
        self.submitted.emit(text)
        return True

    def _recall(self, delta: int) -> bool:
        if not self.history_enabled or not self.history:
            return False
        pos = len(self.history) if self._history_pos is None else self._history_pos
        pos = max(0, min(len(self.history), pos + delta))
        self._history_pos = pos
        self.set_text(self.history[pos] if pos < len(self.history) else "")
        return True

    def on_event(self, ev: Event) -> bool:
        if isinstance(ev, TextEvent):
            self.insert(ev.text)
            return True

        if isinstance(ev, CompositionEvent):
            if ev.text and self.selection():
                sel = self.selection()
                self._replace(sel[0], sel[1], "")
            self.preedit = ev.text
            self.invalidate()
            return True

        if isinstance(ev, KeyEvent):
            k = ev.key
            shift = ev.shift
            if ev.primary and k == Key.A:
                self.select_all()
            elif ev.primary and k == Key.C:
                if self.selection():
                    clipboard_put(self.selected_text())
            elif ev.primary and k == Key.X:
                if self.selection():
                    clipboard_put(self.selected_text())
                    self.backspace()
            elif ev.primary and k == Key.V:
                self.insert(clipboard_get())
            elif k == Key.LEFT:
                sel = self.selection()
                self.move(sel[0] if sel and not shift else self.cursor - 1, shift)
            elif k == Key.RIGHT:
                sel = self.selection()
                self.move(sel[1] if sel and not shift else self.cursor + 1, shift)
            elif k == Key.HOME:
                self.move(0, shift)
            elif k == Key.END:
                self.move(len(self.text), shift)
            elif k == Key.BACKSPACE and not (ev.mod & (Mod.CTRL | Mod.META | Mod.ALT)):
                self.backspace()
            elif k == Key.DELETE:
                self.delete()
            elif ev.is_enter and not ev.mod:
                return self._submit()
            elif k == Key.UP and not ev.mod:
                return self._recall(-1)
            elif k == Key.DOWN and not ev.mod:
                return self._recall(+1)
            else:
                return False
            return True

        if isinstance(ev, MouseEvent):
            if ev.kind == "down" and ev.button == 1:
                if ev.clicks >= 2:
                    self.select_all()
                else:
                    self.move(self.index_at(ev.cx), bool(ev.mod & Mod.SHIFT))
                self._dragging = True
                return True
            if ev.kind == "move" and self._dragging:
                self.move(self.index_at(ev.cx), True)
                return True
            if ev.kind == "up" and ev.button == 1:
                self._dragging = False
                return True

        if isinstance(ev, FocusEvent):
            self._dragging = False
            self.invalidate()
        return False
