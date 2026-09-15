"""Single-line text label."""

from __future__ import annotations

from retroui.core.geometry import Rect
from retroui.core.wcwidth import str_width, truncate
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
        **kw,
    ):
        super().__init__(**kw)
        self.text = str(text)
        self.fg = fg
        self.bg = bg
        self.align = align
        self.bold = bold

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
        p.text(x, 0, s, fg, bg, Attr.BOLD if self.bold else 0)
