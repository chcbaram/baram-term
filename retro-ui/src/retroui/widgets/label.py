"""Single-line text label."""

from __future__ import annotations

from typing import Callable

from retroui.core.geometry import Rect
from retroui.core.signal import Signal
from retroui.core.wcwidth import str_width, truncate
from retroui.input.events import Event, MouseEvent
from retroui.render.cellbuffer import Attr
from retroui.render.painter import Painter
from retroui.widgets.base import RGB, SizeHint, Widget


class Label(Widget):
    def __init__(
        self,
        text: str = "",
        *,
        fg: str | RGB = "fg",
        bg: str | RGB = "bg",
        align: str = "left",
        bold: bool = False,
        on_click: Callable[[], None] | None = None,
        **kw,
    ):
        super().__init__(**kw)
        self.text = str(text)
        self.fg = fg
        self.bg = bg
        self.align = align
        self.bold = bold
        # 누를 수 있는 글자 (상태줄 항목 등). 포커스는 가져가지 않는다: 입력은 원래 위젯에 남는다
        self.clicked = Signal()
        if on_click is not None:
            self.clicked.connect(on_click)

    @property
    def cursor(self) -> str | None:
        return "hand" if len(self.clicked) else None

    def set_text(self, text: object) -> None:
        text = str(text)
        if text == self.text:
            return
        width_changed = str_width(text) != str_width(self.text)
        self.text = text
        if width_changed:
            self.relayout()
        self.invalidate()

    def size_hint(self) -> SizeHint:
        w = str_width(self.text)
        return SizeHint(min(w, 1), 1, w, 1, max_h=1)

    def paint(self, p: Painter) -> None:
        w = self.rect.w
        fg = self.color(self.fg) if self.enabled else self.palette.disabled
        bg = self.color(self.bg)
        p.fill(Rect(0, 0, w, self.rect.h), " ", fg, bg)
        s = truncate(self.text, w)
        sw = str_width(s)
        if self.align == "center":
            x = (w - sw) // 2
        elif self.align == "right":
            x = w - sw
        else:
            x = 0
        attr = Attr.BOLD if self.bold else 0
        if self.hovered and len(self.clicked):
            attr |= Attr.UNDERLINE
        p.text(x, 0, s, fg, bg, attr)

    def on_event(self, ev: Event) -> bool:
        if isinstance(ev, MouseEvent) and ev.kind == "down" and ev.button == 1 and self.enabled and len(self.clicked):
            self.clicked.emit()
            return True
        return False
