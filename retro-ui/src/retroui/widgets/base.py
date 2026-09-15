"""Widget tree base class.

위젯의 rect 는 화면 절대 셀 좌표이고, paint() 에 넘어오는 Painter 는 위젯 로컬 좌표다.
이벤트의 cx/cy 는 절대 셀 좌표이므로 필요하면 local_pos() 로 바꿔 쓴다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterator

from retroui.core.geometry import Rect
from retroui.render.painter import Painter
from retroui.theme import DOS_BLUE, Palette, Theme, resolve_color

if TYPE_CHECKING:
    from retroui.app import App
    from retroui.input.events import Event

RGB = tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class SizeHint:
    min_w: int = 0
    min_h: int = 0
    pref_w: int = 0
    pref_h: int = 0
    max_w: int | None = None
    max_h: int | None = None


class Widget:
    focusable = False
    # 포커스가 자손으로 들어오거나 나갈 때 다시 그려야 하는 위젯 (예: 포커스 테두리를 바꾸는 GroupBox)
    repaint_on_focus_within = False

    def __init__(
        self,
        *,
        stretch: int = 0,
        visible: bool = True,
        enabled: bool = True,
        min_size: tuple[int, int] | None = None,
        name: str | None = None,
    ):
        self.parent: Widget | None = None
        self.children: list[Widget] = []
        self.rect = Rect()
        self.stretch = stretch
        self.min_size = min_size
        self.name = name
        self.hovered = False
        self._visible = visible
        self._enabled = enabled
        self._app: App | None = None

    # ---- tree ----------------------------------------------------------

    @property
    def app(self) -> App | None:
        w = self
        while w.parent is not None:
            w = w.parent
        return w._app

    def add(self, child: Widget) -> Widget:
        if child.parent is not None:
            child.parent.remove(child)
        child.parent = self
        self.children.append(child)
        self.relayout()
        return child

    def remove(self, child: Widget) -> None:
        app = self.app
        self.children.remove(child)
        child.parent = None
        if app is not None:
            app._forget(child)
        self.relayout()

    def iter_tree(self) -> Iterator[Widget]:
        """보이는 위젯만 전위 순회 (포커스 순서와 같다)."""
        if not self._visible:
            return
        yield self
        for c in self.children:
            yield from c.iter_tree()

    def is_ancestor_of(self, other: Widget | None) -> bool:
        while other is not None:
            if other is self:
                return True
            other = other.parent
        return False

    def child_at(self, cx: int, cy: int) -> Widget | None:
        if not self._visible or not self.rect.contains(cx, cy):
            return None
        for c in reversed(self.children):
            hit = c.child_at(cx, cy)
            if hit is not None:
                return hit
        return self

    # ---- state ---------------------------------------------------------

    @property
    def visible(self) -> bool:
        return self._visible

    @visible.setter
    def visible(self, value: bool) -> None:
        if value != self._visible:
            self._visible = value
            app = self.app
            if app is not None and not value:
                app._forget(self)
            self.relayout()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        if value != self._enabled:
            self._enabled = value
            app = self.app
            if app is not None and not value and self.is_ancestor_of(app.focus):
                app.set_focus(None)
            self.invalidate()

    @property
    def focused(self) -> bool:
        app = self.app
        return app is not None and app.focus is self

    def has_focus_within(self) -> bool:
        app = self.app
        return app is not None and self.is_ancestor_of(app.focus)

    @property
    def theme(self) -> Theme:
        app = self.app
        return app.theme if app is not None else DOS_BLUE

    @property
    def palette(self) -> Palette:
        return self.theme.palette

    def color(self, c: str | RGB) -> RGB:
        return resolve_color(c, self.palette)

    def local_pos(self, cx: int, cy: int) -> tuple[int, int]:
        return cx - self.rect.x, cy - self.rect.y

    # ---- layout / paint / events (override) ----------------------------

    def size_hint(self) -> SizeHint:
        return SizeHint(1, 1, 1, 1)

    def effective_hint(self) -> SizeHint:
        h = self.size_hint()
        if self.min_size is not None:
            mw, mh = self.min_size
            h = SizeHint(max(h.min_w, mw), max(h.min_h, mh), max(h.pref_w, mw), max(h.pref_h, mh), h.max_w, h.max_h)
        return h

    # 마우스를 올린 채 잠깐 두면 App 이 이 글을 작은 상자로 띄운다 (App.tooltip_delay 초)
    tooltip: str = ""

    def _do_layout(self, rect: Rect) -> None:
        self.rect = rect
        self.layout_children()

    def layout_children(self) -> None:
        for c in self.children:
            c._do_layout(self.rect)

    def paint(self, p: Painter) -> None:
        pass

    def on_event(self, ev: Event) -> bool:
        """이벤트를 처리했으면 True. False 면 부모로 전달된다."""
        return False

    def invalidate(self, rect: Rect | None = None) -> None:
        app = self.app
        if app is not None:
            app.invalidate(self.rect if rect is None else rect)

    def relayout(self) -> None:
        app = self.app
        if app is not None:
            app.request_layout()
