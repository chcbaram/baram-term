"""One-row tab strip: ` HEX │ 부팅절차 │ 센서점검 │ + `.

왼쪽 클릭으로 탭을 고르고, `+` 로 새 탭을 만든다. 오른쪽 클릭은 그 탭의 메뉴(이름 바꾸기/삭제)를 부른다.
포커스를 가져가지 않는다: 탭을 눌러도 키보드 입력은 원래 있던 곳(터미널 등)에 남는다.
"""

from __future__ import annotations

from typing import Callable, Sequence

from retroui.core.geometry import Rect
from retroui.core.signal import Signal
from retroui.core.wcwidth import str_width, truncate
from retroui.input.events import Event, MouseEvent
from retroui.render.painter import Painter
from retroui.widgets.base import SizeHint, Widget

ADD = -1  # tab_at() 이 돌려주는 "+" 자리
_SEP = "│"
_PAD = 1  # 제목 좌우 여백
MIN_TITLE = 4


class TabBar(Widget):
    def __init__(
        self,
        titles: Sequence[str] = (),
        *,
        selected: int = 0,
        add_label: str = "+",
        show_add: bool = True,
        on_select: Callable[[int], None] | None = None,
        on_add: Callable[[], None] | None = None,
        on_menu: Callable[[int, int, int], None] | None = None,
        **kw,
    ):
        super().__init__(**kw)
        self.titles = [str(t) for t in titles]
        self.selected = max(0, min(selected, len(self.titles) - 1)) if self.titles else -1
        self.add_label = add_label
        self._show_add = bool(show_add)
        self.selected_changed = Signal()  # int
        self.add_requested = Signal()
        self.menu_requested = Signal()  # (index, cx, cy)
        if on_select is not None:
            self.selected_changed.connect(on_select)
        if on_add is not None:
            self.add_requested.connect(on_add)
        if on_menu is not None:
            self.menu_requested.connect(on_menu)
        self._spans: list[tuple[int, int, int]] = []  # (시작, 끝, 인덱스 또는 ADD)

    @property
    def cursor(self) -> str | None:
        return "hand"

    @property
    def show_add(self) -> bool:
        return self._show_add

    @show_add.setter
    def show_add(self, on: bool) -> None:
        """탭을 더할 수 없는 상태면 '+' 를 감춘다. 그만큼 제목 폭이 넓어진다."""
        on = bool(on)
        if on != self._show_add:
            self._show_add = on
            self.relayout()
            self.invalidate()

    # ---- model ---------------------------------------------------------

    def set_titles(self, titles: Sequence[str], selected: int | None = None) -> None:
        self.titles = [str(t) for t in titles]
        if selected is not None:
            self.selected = selected
        self.selected = max(0, min(self.selected, len(self.titles) - 1)) if self.titles else -1
        self.relayout()
        self.invalidate()

    def select(self, index: int, emit: bool = True) -> None:
        if not self.titles:
            return
        index = max(0, min(index, len(self.titles) - 1))
        if index != self.selected:
            self.selected = index
            self.invalidate()
            if emit:
                self.selected_changed.emit(index)

    # ---- layout / paint ------------------------------------------------

    def _add_width(self) -> int:
        """'+' 가 차지하는 폭. 감춰 두면 0 이다."""
        return str_width(self.add_label) + 2 * _PAD if self._show_add else 0

    def _title_width(self) -> int:
        """한 탭에 쓸 제목 폭. 좁으면 모든 탭을 같은 폭으로 줄인다."""
        widest = max((str_width(t) for t in self.titles), default=MIN_TITLE)
        room = self.rect.w - (self._add_width() + 1)
        per_tab = room // max(1, len(self.titles)) - (2 * _PAD + 1)
        return max(MIN_TITLE, min(widest, per_tab)) if self.titles else widest

    def size_hint(self) -> SizeHint:
        tabs = sum(str_width(t) + 2 * _PAD + 1 for t in self.titles)
        width = tabs + self._add_width()
        return SizeHint(MIN_TITLE + 4, 1, max(width, MIN_TITLE + 4), 1, max_h=1)

    def paint(self, p: Painter) -> None:
        pal = self.palette
        w = self.rect.w
        p.fill(Rect(0, 0, w, self.rect.h), " ", pal.dim, pal.bg)
        self._spans = []
        title_w = self._title_width()
        x = 0
        for i, title in enumerate(self.titles):
            label = truncate(title, title_w)
            span = str_width(label) + 2 * _PAD
            if x + span > w - self._add_width():
                p.put(max(0, min(x, w - 1)), 0, "…", pal.dim, pal.bg)
                x += 1
                break
            picked = i == self.selected
            fg, bg = (pal.sel_fg, pal.sel_bg) if picked else (pal.fg, pal.bg)
            p.fill(Rect(x, 0, span, 1), " ", fg, bg)
            p.text(x + _PAD, 0, label, fg, bg)
            self._spans.append((x, x + span, i))
            x += span
            if i + 1 < len(self.titles):
                p.put(x, 0, _SEP, pal.dim, pal.bg)
                x += 1
        if self._show_add and x < w:
            p.put(x, 0, _SEP, pal.dim, pal.bg)
            add_span = str_width(self.add_label) + 2 * _PAD
            p.text(x + 1 + _PAD, 0, self.add_label, pal.accent, pal.bg)
            self._spans.append((x + 1, x + 1 + add_span, ADD))

    # ---- mouse ---------------------------------------------------------

    def tab_at(self, cx: int) -> int | None:
        col = cx - self.rect.x
        for start, end, index in self._spans:
            if start <= col < end:
                return index
        return None

    def on_event(self, ev: Event) -> bool:
        if not isinstance(ev, MouseEvent) or ev.kind != "down":
            return isinstance(ev, MouseEvent)
        index = self.tab_at(ev.cx)
        if index is None:
            return True
        if index == ADD:
            if ev.button == 1:
                self.add_requested.emit()
            return True
        if ev.button == 1:
            self.select(index)
        elif ev.button == 3:
            self.menu_requested.emit(index, ev.cx, ev.cy)
        return True
