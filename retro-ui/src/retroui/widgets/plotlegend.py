"""Clickable legend for a LivePlot.

이름을 누르면 그 시리즈를 보이거나 숨긴다 (Arduino IDE 시리얼 플로터의 체크박스처럼).
LivePlot(header=False) 와 함께 쓰면 범례를 버튼 등과 같은 줄에 둘 수 있다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from retroui.core.geometry import Rect
from retroui.core.wcwidth import str_width, truncate
from retroui.input.events import Event, MouseEvent
from retroui.render.painter import Painter
from retroui.widgets.base import SizeHint, Widget

if TYPE_CHECKING:
    from retroui.widgets.plot import LivePlot, Series

_GAP = 2


class PlotLegend(Widget):
    def __init__(self, plot: LivePlot, *, stretch: int = 1, **kw):
        super().__init__(stretch=stretch, **kw)
        self.plot = plot
        self._spans: list[tuple[int, int, Series]] = []
        plot.series_changed.connect(self._on_series_changed)

    @property
    def cursor(self) -> str | None:
        return "hand" if self.plot.series else None

    def _on_series_changed(self) -> None:
        self.relayout()
        self.invalidate()

    def size_hint(self) -> SizeHint:
        w = sum(str_width(s.name) + 1 + _GAP for s in self.plot.series)
        return SizeHint(1, 1, max(1, w), 1, max_h=1)

    def paint(self, p: Painter) -> None:
        pal = self.palette
        w = self.rect.w
        p.fill(Rect(0, 0, w, self.rect.h), " ", pal.fg, pal.bg)
        self._spans = []
        x = 0
        for i, s in enumerate(self.plot.series):
            item_w = str_width(s.name) + 1
            if x + item_w > w:
                if x < w:
                    p.put(min(x, w - 1), 0, "…", pal.dim, pal.bg)
                break
            color = self.plot.series_color(i, s) if s.visible else pal.disabled
            p.put(x, 0, "■" if s.visible else "□", color, pal.bg)
            p.text(x + 1, 0, truncate(s.name, w - x - 1), color, pal.bg)
            self._spans.append((x, x + item_w, s))
            x += item_w + _GAP

    def on_event(self, ev: Event) -> bool:
        if isinstance(ev, MouseEvent) and ev.kind == "down" and ev.button == 1:
            col = ev.cx - self.rect.x
            for x0, x1, s in self._spans:
                if x0 <= col < x1:
                    self.plot.set_series_visible(s, not s.visible)
                    return True
        return False
