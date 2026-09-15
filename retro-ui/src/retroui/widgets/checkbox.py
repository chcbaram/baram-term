"""Check box: `[x] label`."""

from __future__ import annotations

from typing import Callable

from retroui.core.geometry import Rect
from retroui.core.signal import Signal
from retroui.core.wcwidth import str_width, truncate
from retroui.input.events import Event, Key, KeyEvent, MouseEvent
from retroui.render.painter import Painter
from retroui.widgets.base import SizeHint, Widget


class CheckBox(Widget):
    focusable = True

    def __init__(self, text: str, checked: bool = False, on_toggle: Callable[[bool], None] | None = None, **kw):
        super().__init__(**kw)
        self.text = text
        self.checked = checked
        self.toggled = Signal()
        if on_toggle is not None:
            self.toggled.connect(on_toggle)
        self._armed = False

    def set_checked(self, checked: bool, emit: bool = True) -> None:
        if checked == self.checked:
            return
        self.checked = checked
        self.invalidate()
        if emit:
            self.toggled.emit(checked)

    def toggle(self) -> None:
        if self.enabled:
            self.set_checked(not self.checked)

    def activate(self) -> None:
        self.toggle()

    def size_hint(self) -> SizeHint:
        w = 4 + str_width(self.text)
        return SizeHint(3, 1, w, 1, max_h=1)

    def paint(self, p: Painter) -> None:
        pal = self.palette
        if not self.enabled:
            fg = pal.disabled
        elif self.focused:
            fg = pal.accent
        else:
            fg = pal.fg
        bg = pal.hover_bg if self.hovered and self.enabled else pal.bg
        p.fill(Rect(0, 0, self.rect.w, self.rect.h), " ", fg, bg)
        p.text(0, 0, "[x]" if self.checked else "[ ]", fg, bg)
        p.text(4, 0, truncate(self.text, max(0, self.rect.w - 4)), fg, bg)

    def on_event(self, ev: Event) -> bool:
        if isinstance(ev, MouseEvent) and ev.button == 1:
            if ev.kind == "down":
                self._armed = True
                return True
            if ev.kind == "up" and self._armed:
                self._armed = False
                if self.rect.contains(ev.cx, ev.cy):
                    self.toggle()
                return True
        elif isinstance(ev, KeyEvent) and ev.key == Key.SPACE and not ev.mod:
            self.toggle()
            return True
        return False
