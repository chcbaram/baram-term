"""Two widgets with a draggable boundary (QSplitter-like): VSplit (위아래), HSplit (좌우).

따로 손잡이 줄/칸을 두지 않는다: 앞 위젯의 마지막 줄(칸)과 뒤 위젯의 첫 줄(칸), 보통 맞닿은 두 테두리를 잡고 끈다.
화면을 더 쓰지 않고, 테두리 상자끼리 붙어 있는 TUI 배치에서 자연스럽다.
크기는 비율로 기억한다: 창이나 글자 크기가 바뀌어도 나눈 모양이 유지된다.
"""

from __future__ import annotations

from typing import Callable

from retroui.core.geometry import Rect
from retroui.core.signal import Signal
from retroui.input.events import Event, MouseEvent
from retroui.widgets.base import SizeHint, Widget


class _Split(Widget):
    """first(위/왼쪽) 와 second(아래/오른쪽) 를 비율로 나눈다."""

    vertical = True
    cursor_name = "resize_ns"

    def __init__(
        self,
        first: Widget,
        second: Widget,
        *,
        ratio: float = 0.5,
        default_ratio: float | None = None,
        min_first: int = 3,
        min_second: int = 3,
        on_change: Callable[[float], None] | None = None,
        stretch: int = 1,
        **kw,
    ):
        super().__init__(stretch=stretch, **kw)
        self.first = self.add(first)
        self.second = self.add(second)
        self.ratio = min(0.95, max(0.05, float(ratio)))
        self.default_ratio = self.ratio if default_ratio is None else default_ratio
        self.min_first = min_first
        self.min_second = min_second
        self.changed = Signal()  # float: 끌기를 마쳤을 때 (끄는 중에는 내지 않는다: 설정 저장이 매번 일어나지 않게)
        if on_change is not None:
            self.changed.connect(on_change)
        self._drag: int | None = None  # 잡은 줄(칸)과 경계 사이 거리

    @property
    def split_pos(self) -> int:
        """뒤 위젯의 첫 줄/칸 (절대 좌표)."""
        return self.second.rect.y if self.vertical else self.second.rect.x

    def set_ratio(self, ratio: float) -> None:
        ratio = min(1.0, max(0.0, ratio))
        if ratio != self.ratio:
            self.ratio = ratio
            self.relayout()
            self.invalidate()

    def _first_size(self, total: int) -> int:
        if not self.second.visible:
            return total
        size = round(total * self.ratio)
        lo, hi = self.min_first, total - self.min_second
        if lo <= hi:
            size = max(lo, min(hi, size))
        return max(0, min(total, size))

    # ---- layout --------------------------------------------------------

    def size_hint(self) -> SizeHint:
        a = self.first.effective_hint()
        if not self.second.visible:
            if self.vertical:
                return SizeHint(a.min_w, max(a.min_h, self.min_first), a.pref_w, a.pref_h)
            return SizeHint(max(a.min_w, self.min_first), a.min_h, a.pref_w, a.pref_h)
        b = self.second.effective_hint()
        span = self.min_first + self.min_second
        if self.vertical:
            return SizeHint(max(a.min_w, b.min_w), span, max(a.pref_w, b.pref_w), a.pref_h + b.pref_h)
        return SizeHint(span, max(a.min_h, b.min_h), a.pref_w + b.pref_w, max(a.pref_h, b.pref_h))

    def layout_children(self) -> None:
        r = self.rect
        if self.vertical:
            size = self._first_size(r.h)
            self.first._do_layout(Rect(r.x, r.y, r.w, size))
            if self.second.visible:
                self.second._do_layout(Rect(r.x, r.y + size, r.w, r.h - size))
        else:
            size = self._first_size(r.w)
            self.first._do_layout(Rect(r.x, r.y, size, r.h))
            if self.second.visible:
                self.second._do_layout(Rect(r.x + size, r.y, r.w - size, r.h))

    # ---- mouse ---------------------------------------------------------

    def _total(self) -> int:
        return self.rect.h if self.vertical else self.rect.w

    def _at(self, ev: MouseEvent) -> int:
        return ev.cy if self.vertical else ev.cx

    def on_handle(self, pos: int) -> bool:
        return self.second.visible and self._total() > 0 and pos in (self.split_pos - 1, self.split_pos)

    def cursor_at(self, cx: int, cy: int) -> str | None:
        pos = cy if self.vertical else cx
        if self._drag is not None or (self.rect.contains(cx, cy) and self.on_handle(pos)):
            return self.cursor_name
        return None

    def _move_to(self, split_pos: int) -> None:
        total = self._total()
        if total <= 0:
            return
        size = split_pos - (self.rect.y if self.vertical else self.rect.x)
        lo, hi = self.min_first, total - self.min_second
        if lo <= hi:
            size = max(lo, min(hi, size))
        self.set_ratio(size / total)

    def on_event(self, ev: Event) -> bool:
        if not isinstance(ev, MouseEvent):
            return False
        if ev.kind == "down" and ev.button == 1 and self.on_handle(self._at(ev)):
            if ev.clicks >= 2:
                self._drag = None
                self.set_ratio(self.default_ratio)
                self.changed.emit(self.ratio)
                return True
            self._drag = self._at(ev) - self.split_pos
            return True
        if ev.kind == "move" and self._drag is not None:
            self._move_to(self._at(ev) - self._drag)
            return True
        if ev.kind == "up" and ev.button == 1 and self._drag is not None:
            self._drag = None
            self.changed.emit(self.ratio)
            return True
        return False


class VSplit(_Split):
    vertical = True
    cursor_name = "resize_ns"

    def __init__(self, top: Widget, bottom: Widget, *, min_top: int = 3, min_bottom: int = 3, **kw):
        super().__init__(top, bottom, min_first=min_top, min_second=min_bottom, **kw)

    # 예전 이름 (위/아래)
    @property
    def top(self) -> Widget:
        return self.first

    @property
    def bottom(self) -> Widget:
        return self.second

    @property
    def split_y(self) -> int:
        return self.split_pos

    @property
    def min_top(self) -> int:
        return self.min_first

    @property
    def min_bottom(self) -> int:
        return self.min_second


class HSplit(_Split):
    vertical = False
    cursor_name = "resize_ew"

    def __init__(self, left: Widget, right: Widget, *, min_left: int = 8, min_right: int = 8, **kw):
        super().__init__(left, right, min_first=min_left, min_second=min_right, **kw)

    @property
    def left(self) -> Widget:
        return self.first

    @property
    def right(self) -> Widget:
        return self.second

    @property
    def split_x(self) -> int:
        return self.split_pos

    @property
    def min_left(self) -> int:
        return self.min_first

    @property
    def min_right(self) -> int:
        return self.min_second
