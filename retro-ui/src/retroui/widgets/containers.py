"""Box layouts in cell units."""

from __future__ import annotations

from retroui.core.geometry import Rect
from retroui.core.layout import distribute
from retroui.widgets.base import SizeHint, Widget


class Box(Widget):
    horizontal = True

    def __init__(self, *children: Widget | None, spacing: int = 0, margin: int = 0, align: str = "fill", **kw):
        super().__init__(**kw)
        self.spacing = spacing
        self.margin = margin
        self.align = align  # 교차 축 정렬: fill | start | center | end
        for c in children:
            if c is not None:
                self.add(c)

    def _visible_children(self) -> list[Widget]:
        return [c for c in self.children if c.visible]

    def size_hint(self) -> SizeHint:
        hints = [c.effective_hint() for c in self._visible_children()]
        gap = self.spacing * max(0, len(hints) - 1)
        m2 = self.margin * 2
        if self.horizontal:
            return SizeHint(
                sum(h.min_w for h in hints) + gap + m2,
                max((h.min_h for h in hints), default=0) + m2,
                sum(h.pref_w for h in hints) + gap + m2,
                max((h.pref_h for h in hints), default=0) + m2,
            )
        return SizeHint(
            max((h.min_w for h in hints), default=0) + m2,
            sum(h.min_h for h in hints) + gap + m2,
            max((h.pref_w for h in hints), default=0) + m2,
            sum(h.pref_h for h in hints) + gap + m2,
        )

    def layout_children(self) -> None:
        kids = self._visible_children()
        if not kids:
            return
        inner = self.rect.inset(self.margin)
        hints = [c.effective_hint() for c in kids]
        if self.horizontal:
            sizes = distribute(inner.w, [(h.min_w, h.pref_w, c.stretch) for c, h in zip(kids, hints)], self.spacing)
            cross_total = inner.h
        else:
            sizes = distribute(inner.h, [(h.min_h, h.pref_h, c.stretch) for c, h in zip(kids, hints)], self.spacing)
            cross_total = inner.w

        pos = inner.x if self.horizontal else inner.y
        for c, h, size in zip(kids, hints, sizes):
            cmax = h.max_h if self.horizontal else h.max_w
            cpref = h.pref_h if self.horizontal else h.pref_w
            if self.align == "fill":
                cs = cross_total if cmax is None else min(cross_total, cmax)
            else:
                cs = min(cross_total, cpref)
            if self.align == "center":
                off = (cross_total - cs) // 2
            elif self.align == "end":
                off = cross_total - cs
            else:
                off = 0
            if self.horizontal:
                c._do_layout(Rect(pos, inner.y + off, size, cs))
            else:
                c._do_layout(Rect(inner.x + off, pos, cs, size))
            pos += size + self.spacing


class HBox(Box):
    horizontal = True


class VBox(Box):
    horizontal = False


class Spacer(Widget):
    def __init__(self, size: int = 0, stretch: int = 1, **kw):
        super().__init__(stretch=stretch, **kw)
        self.size = size

    def size_hint(self) -> SizeHint:
        return SizeHint(self.size, self.size, self.size, self.size)
