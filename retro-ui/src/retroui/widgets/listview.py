"""Scrollable list with an optional right-aligned detail column (file lists, pickers).

ListPopup 은 잠깐 떠서 고르는 팝업이고, ListView 는 대화상자 안에 계속 놓이는 목록이다.
"""

from __future__ import annotations

from typing import Callable, Sequence

from retroui.core.geometry import Rect
from retroui.core.signal import Signal
from retroui.core.wcwidth import str_width, truncate
from retroui.input.events import Event, FocusEvent, Key, KeyEvent, Mod, MouseEvent, WheelEvent
from retroui.render.painter import Painter
from retroui.widgets.base import SizeHint, Widget
from retroui.widgets.scrollbar import ScrollBar


class ListView(Widget):
    focusable = True

    def __init__(
        self,
        items: Sequence[object] = (),
        details: Sequence[object] | None = None,
        *,
        selected: int = 0,
        on_activate: Callable[[int], None] | None = None,
        on_select: Callable[[int], None] | None = None,
        stretch: int = 1,
        **kw,
    ):
        super().__init__(stretch=stretch, **kw)
        self.items: list[str] = []
        self.details: list[str] = []
        self.selected = -1
        self.top = 0
        self.activated = Signal()  # int: Enter / 더블클릭
        self.selection_changed = Signal()  # int: 사용자가 선택을 옮겼을 때
        if on_activate is not None:
            self.activated.connect(on_activate)
        if on_select is not None:
            self.selection_changed.connect(on_select)
        self.scrollbar = ScrollBar(on_scroll=self._on_scroll)
        self.add(self.scrollbar)
        self.set_items(items, details, selected)

    # ---- model ---------------------------------------------------------

    def set_items(self, items: Sequence[object], details: Sequence[object] | None = None, selected: int = 0) -> None:
        """목록을 바꾼다. selection_changed 는 내지 않는다 (프로그램이 바꾼 것이므로)."""
        self.items = [str(i) for i in items]
        details = [str(d) for d in details] if details is not None else []
        self.details = (details + [""] * len(self.items))[: len(self.items)]
        self.selected = max(0, min(selected, len(self.items) - 1)) if self.items else -1
        self.top = 0
        self._ensure_visible()
        self._sync()
        self.relayout()
        self.invalidate()

    @property
    def current(self) -> str | None:
        return self.items[self.selected] if 0 <= self.selected < len(self.items) else None

    @property
    def rows(self) -> int:
        return max(1, self.rect.h)

    def select(self, index: int, emit: bool = True) -> None:
        if not self.items:
            return
        index = max(0, min(index, len(self.items) - 1))
        changed = index != self.selected
        self.selected = index
        self._ensure_visible()
        self._sync()
        self.invalidate()
        if changed and emit:
            self.selection_changed.emit(index)

    def _ensure_visible(self) -> None:
        rows = self.rows
        if self.selected >= 0:
            if self.selected < self.top:
                self.top = self.selected
            elif self.selected >= self.top + rows:
                self.top = self.selected - rows + 1
        self.top = max(0, min(self.top, max(0, len(self.items) - rows)))

    def _scroll(self, delta: int) -> None:
        top = max(0, min(self.top + delta, max(0, len(self.items) - self.rows)))
        if top != self.top:
            self.top = top
            self._sync()
            self.invalidate()

    def _sync(self) -> None:
        self.scrollbar.set_range(len(self.items), self.rows, self.top)

    def _on_scroll(self, pos: int) -> None:
        self.top = pos
        self.invalidate()

    # ---- layout / paint ------------------------------------------------

    def size_hint(self) -> SizeHint:
        w = max((str_width(i) + (str_width(d) + 2 if d else 0) for i, d in zip(self.items, self.details)), default=10) + 3
        return SizeHint(8, 3, w, min(max(len(self.items), 3), 12))

    def _do_layout(self, rect: Rect) -> None:
        super()._do_layout(rect)
        self._ensure_visible()
        self._sync()

    def layout_children(self) -> None:
        self.scrollbar._do_layout(Rect(self.rect.right - 1, self.rect.y, 1, self.rect.h))

    def paint(self, p: Painter) -> None:
        pal = self.palette
        w = max(0, self.rect.w - 1)  # 오른쪽 한 칸은 스크롤바
        h = self.rect.h
        p.fill(Rect(0, 0, w, h), " ", pal.input_fg, pal.input_bg)
        for r in range(h):
            i = self.top + r
            if i >= len(self.items):
                break
            if i == self.selected:
                # 포커스가 없을 때도 어느 줄인지는 보이게 옅게 칠한다
                fg, bg = (pal.sel_fg, pal.sel_bg) if self.focused else (pal.fg, pal.hover_bg)
                p.fill(Rect(0, r, w, 1), " ", fg, bg)
                detail_fg = fg
            else:
                fg, bg = pal.input_fg, pal.input_bg
                detail_fg = pal.dim
            room = w - 2
            detail = self.details[i]
            dw = str_width(detail)
            if detail and dw + 2 < room:
                p.text(w - 1 - dw, r, detail, detail_fg, bg)
                room -= dw + 2
            p.text(1, r, truncate(self.items[i], max(0, room)), fg, bg)

    # ---- events --------------------------------------------------------

    def _row_at(self, cy: int) -> int | None:
        i = self.top + cy - self.rect.y
        return i if 0 <= cy - self.rect.y < self.rect.h and i < len(self.items) else None

    def _type_ahead(self, ch: str) -> None:
        """글자를 누르면 그 글자로 시작하는 다음 항목으로 (같은 글자를 계속 누르면 돌아가며)."""
        n = len(self.items)
        ch = ch.lower()
        start = self.selected if self.selected >= 0 else -1
        for step in range(1, n + 1):
            i = (start + step) % n
            if self.items[i].lower().startswith(ch):
                self.select(i)
                return

    def on_event(self, ev: Event) -> bool:
        if isinstance(ev, KeyEvent):
            if ev.mod & (Mod.CTRL | Mod.META | Mod.ALT):
                return False
            k = ev.key
            page = max(1, self.rows - 1)
            if k == Key.UP:
                self.select(self.selected - 1)
            elif k == Key.DOWN:
                self.select(self.selected + 1)
            elif k == Key.PAGEUP:
                self.select(self.selected - page)
            elif k == Key.PAGEDOWN:
                self.select(self.selected + page)
            elif k == Key.HOME:
                self.select(0)
            elif k == Key.END:
                self.select(len(self.items) - 1)
            elif ev.is_enter:
                if self.selected < 0:
                    return False
                self.activated.emit(self.selected)
            elif len(ev.name) == 1 and ev.name.isprintable() and ev.name != " ":
                self._type_ahead(ev.name)
            else:
                return False
            return True
        if isinstance(ev, MouseEvent):
            if ev.kind == "down" and ev.button == 1:
                i = self._row_at(ev.cy)
                if i is not None:
                    self.select(i)
                    if ev.clicks >= 2:
                        self.activated.emit(i)
                return True
            return ev.kind == "up"
        if isinstance(ev, WheelEvent):
            self._scroll(-int(round(ev.dy * 3)) or (-1 if ev.dy > 0 else 1))
            return True
        if isinstance(ev, FocusEvent):
            self.invalidate()
        return False
