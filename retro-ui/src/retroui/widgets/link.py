"""Clickable text link. Opens the URL in the default browser unless on_click is given."""

from __future__ import annotations

import webbrowser
from typing import Callable

from retroui.core.geometry import Rect
from retroui.core.signal import Signal
from retroui.core.wcwidth import str_width, truncate
from retroui.input.events import Event, FocusEvent, Key, KeyEvent, MouseEvent
from retroui.render.cellbuffer import Attr
from retroui.render.painter import Painter
from retroui.widgets.label import Label


class Link(Label):
    focusable = True

    def __init__(self, text: str, url: str | None = None, *, on_click: Callable[[str], None] | None = None, **kw):
        kw.setdefault("fg", "accent")
        super().__init__(text, **kw)
        self.url = url if url is not None else str(text)
        self.clicked = Signal()  # str: url
        if on_click is not None:
            self.clicked.connect(on_click)
        self._armed = False

    def activate(self) -> None:
        if len(self.clicked):
            self.clicked.emit(self.url)
            return
        try:
            webbrowser.open(self.url)
        except webbrowser.Error:
            pass  # 브라우저를 찾지 못해도 앱은 계속 (주소는 화면에 보인다)

    def paint(self, p: Painter) -> None:
        pal = self.palette
        w = self.rect.w
        if self.focused:
            fg, bg = pal.sel_fg, pal.sel_bg
        else:
            fg = self.color(self.fg) if self.enabled else pal.disabled
            bg = self.color(self.bg)
        attr = Attr.UNDERLINE | (Attr.BOLD if self.hovered or self.bold else 0)
        p.fill(Rect(0, 0, w, self.rect.h), " ", fg, bg)
        s = truncate(self.text, w)
        sw = str_width(s)
        x = (w - sw) // 2 if self.align == "center" else w - sw if self.align == "right" else 0
        p.text(x, 0, s, fg, bg, attr)

    def on_event(self, ev: Event) -> bool:
        if isinstance(ev, MouseEvent) and ev.button == 1:
            if ev.kind == "down":
                self._armed = True
                return True
            if ev.kind == "up":
                # 누른 채 링크 밖으로 끌고 나가서 떼면 열지 않는다
                if self._armed and self.rect.contains(ev.cx, ev.cy):
                    self.activate()
                self._armed = False
                return True
        if isinstance(ev, KeyEvent) and not ev.mod and (ev.is_enter or ev.key == Key.SPACE):
            self.activate()
            return True
        if isinstance(ev, FocusEvent):
            self.invalidate()
        return False
