"""Bordered containers: GroupBox (titled) and Frame."""

from __future__ import annotations

from retroui.core.geometry import Rect
from retroui.core.wcwidth import str_width
from retroui.render.painter import Painter
from retroui.theme import BoxStyle
from retroui.widgets.base import SizeHint, Widget


class GroupBox(Widget):
    repaint_on_focus_within = True

    def __init__(self, title: str = "", child: Widget | None = None, *, box: BoxStyle | None = None, **kw):
        super().__init__(**kw)
        self.title = title
        self.box = box
        if child is not None:
            self.add(child)

    def set_title(self, title: str) -> None:
        if title != self.title:
            self.title = title
            self.invalidate()

    def size_hint(self) -> SizeHint:
        kids = [c.effective_hint() for c in self.children if c.visible]
        h = kids[0] if kids else SizeHint()
        title_w = str_width(self.title) + 6 if self.title else 2
        return SizeHint(h.min_w + 2, h.min_h + 2, max(h.pref_w + 2, title_w), h.pref_h + 2)

    def layout_children(self) -> None:
        inner = self.rect.inset(1)
        for c in self.children:
            c._do_layout(inner)

    def paint(self, p: Painter) -> None:
        theme = self.theme
        pal = theme.palette
        if self.has_focus_within():
            style, border = theme.box_focus, pal.border_focus
        else:
            style, border = self.box or theme.box, pal.border
        p.box(Rect(0, 0, self.rect.w, self.rect.h), style, border, pal.bg, title=self.title or None, title_fg=pal.accent)


class Frame(GroupBox):
    def __init__(self, child: Widget | None = None, **kw):
        super().__init__("", child, **kw)
