"""Two widgets stacked vertically with a draggable boundary (QSplitter-like).

따로 손잡이 줄을 두지 않는다: 위 위젯의 마지막 줄과 아래 위젯의 첫 줄(보통 두 테두리 줄)을 잡고 끈다.
화면 줄을 더 쓰지 않고, 테두리 상자끼리 붙어 있는 TUI 배치에서 자연스럽다.
높이는 비율로 기억한다: 창이나 글자 크기가 바뀌어도 나눈 모양이 유지된다.
"""

from __future__ import annotations

from typing import Callable

from retroui.core.geometry import Rect
from retroui.core.signal import Signal
from retroui.input.events import Event, MouseEvent
from retroui.widgets.base import SizeHint, Widget


class VSplit(Widget):
    def __init__(
        self,
        top: Widget,
        bottom: Widget,
        *,
        ratio: float = 0.5,
        default_ratio: float | None = None,
        min_top: int = 3,
        min_bottom: int = 3,
        on_change: Callable[[float], None] | None = None,
        stretch: int = 1,
        **kw,
    ):
        super().__init__(stretch=stretch, **kw)
        self.top = self.add(top)
        self.bottom = self.add(bottom)
        self.ratio = min(0.95, max(0.05, float(ratio)))
        self.default_ratio = self.ratio if default_ratio is None else default_ratio
        self.min_top = min_top
        self.min_bottom = min_bottom
        self.changed = Signal()  # float: 끌기를 마쳤을 때 (끄는 중에는 내지 않는다: 설정 저장이 매번 일어나지 않게)
        if on_change is not None:
            self.changed.connect(on_change)
        self._drag: int | None = None  # 잡은 줄과 경계(아래 위젯 첫 줄) 사이 거리

    @property
    def split_y(self) -> int:
        """아래 위젯의 첫 줄 (절대 행)."""
        return self.bottom.rect.y

    def set_ratio(self, ratio: float) -> None:
        ratio = min(1.0, max(0.0, ratio))
        if ratio != self.ratio:
            self.ratio = ratio
            self.relayout()
            self.invalidate()

    def _top_height(self, h: int) -> int:
        if not self.bottom.visible:
            return h
        th = round(h * self.ratio)
        lo, hi = self.min_top, h - self.min_bottom
        if lo <= hi:
            th = max(lo, min(hi, th))
        return max(0, min(h, th))

    # ---- layout --------------------------------------------------------

    def size_hint(self) -> SizeHint:
        t = self.top.effective_hint()
        if not self.bottom.visible:
            return SizeHint(t.min_w, max(t.min_h, self.min_top), t.pref_w, t.pref_h)
        b = self.bottom.effective_hint()
        return SizeHint(
            max(t.min_w, b.min_w), self.min_top + self.min_bottom, max(t.pref_w, b.pref_w), t.pref_h + b.pref_h
        )

    def layout_children(self) -> None:
        r = self.rect
        th = self._top_height(r.h)
        self.top._do_layout(Rect(r.x, r.y, r.w, th))
        if self.bottom.visible:
            self.bottom._do_layout(Rect(r.x, r.y + th, r.w, r.h - th))

    # ---- mouse ---------------------------------------------------------

    def on_handle(self, cy: int) -> bool:
        return self.bottom.visible and self.rect.h > 0 and cy in (self.split_y - 1, self.split_y)

    def cursor_at(self, cx: int, cy: int) -> str | None:
        if self._drag is not None or (self.rect.contains(cx, cy) and self.on_handle(cy)):
            return "resize_ns"
        return None

    def _move_to(self, split_row: int) -> None:
        r = self.rect
        if r.h <= 0:
            return
        th = split_row - r.y
        lo, hi = self.min_top, r.h - self.min_bottom
        if lo <= hi:
            th = max(lo, min(hi, th))
        self.set_ratio(th / r.h)

    def on_event(self, ev: Event) -> bool:
        if not isinstance(ev, MouseEvent):
            return False
        if ev.kind == "down" and ev.button == 1 and self.on_handle(ev.cy):
            if ev.clicks >= 2:
                self._drag = None
                self.set_ratio(self.default_ratio)
                self.changed.emit(self.ratio)
                return True
            self._drag = ev.cy - self.split_y
            return True
        if ev.kind == "move" and self._drag is not None:
            self._move_to(ev.cy - self._drag)
            return True
        if ev.kind == "up" and ev.button == 1 and self._drag is not None:
            self._drag = None
            self.changed.emit(self.ratio)
            return True
        return False
