"""ComboBox and the scrollable ListPopup it opens."""

from __future__ import annotations

from typing import Callable, Sequence

from retroui.core.geometry import Rect
from retroui.core.signal import Signal
from retroui.core.wcwidth import str_width, truncate
from retroui.input.events import Event, Key, KeyEvent, Mod, MouseEvent, WheelEvent
from retroui.render.painter import Painter
from retroui.widgets.base import SizeHint, Widget
from retroui.widgets.popup import Popup


class ListPopup(Popup):
    focusable = True

    def __init__(
        self,
        items: Sequence[str],
        selected: int = 0,
        *,
        on_choose: Callable[[int], None] | None = None,
        visible_rows: int = 10,
    ):
        super().__init__()
        self.items = [str(i) for i in items]
        self.selected = max(0, min(selected, len(self.items) - 1)) if self.items else -1
        self.top = 0
        self.visible_rows = visible_rows
        self.on_choose = on_choose

    @property
    def rows(self) -> int:
        return max(0, self.rect.h - 2)

    def size_hint(self) -> SizeHint:
        w = max((str_width(i) for i in self.items), default=4) + 4
        h = min(len(self.items), self.visible_rows) + 2
        return SizeHint(w, h, w, h)

    def _ensure_visible(self) -> None:
        rows = self.rows or self.visible_rows
        if self.selected < self.top:
            self.top = self.selected
        elif self.selected >= self.top + rows:
            self.top = self.selected - rows + 1
        self.top = max(0, min(self.top, max(0, len(self.items) - rows)))

    def select(self, index: int) -> None:
        if not self.items:
            return
        index = max(0, min(index, len(self.items) - 1))
        if index != self.selected:
            self.selected = index
            self._ensure_visible()
            self.invalidate()

    def choose(self, index: int) -> None:
        self.close()
        if self.on_choose is not None and 0 <= index < len(self.items):
            self.on_choose(index)

    def _do_layout(self, rect: Rect) -> None:
        super()._do_layout(rect)
        self._ensure_visible()

    def paint(self, p: Painter) -> None:
        theme = self.theme
        pal = theme.palette
        w, h = self.rect.w, self.rect.h
        p.box(Rect(0, 0, w, h), theme.box, pal.border, pal.bg)
        for r in range(self.rows):
            i = self.top + r
            if i >= len(self.items):
                break
            if i == self.selected:
                fg, bg = pal.sel_fg, pal.sel_bg
            else:
                fg, bg = pal.fg, pal.bg
            p.fill(Rect(1, r + 1, w - 2, 1), " ", fg, bg)
            p.text(2, r + 1, truncate(self.items[i], w - 4), fg, bg)
        if len(self.items) > self.rows:
            if self.top > 0:
                p.put(w - 1, 1, "▲", pal.accent, pal.bg)
            if self.top + self.rows < len(self.items):
                p.put(w - 1, h - 2, "▼", pal.accent, pal.bg)

    def _row_at(self, cx: int, cy: int) -> int | None:
        if not self.rect.inset(1).contains(cx, cy):
            return None
        i = self.top + cy - self.rect.y - 1
        return i if i < len(self.items) else None

    def on_event(self, ev: Event) -> bool:
        if isinstance(ev, KeyEvent):
            if ev.alt or ev.mod & (Mod.CTRL | Mod.META):
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
            elif ev.is_enter or k == Key.SPACE:
                self.choose(self.selected)
            elif k == Key.ESCAPE:
                self.close()
            return True
        if isinstance(ev, MouseEvent):
            row = self._row_at(ev.cx, ev.cy)
            if ev.kind in ("move", "down"):
                if row is not None:
                    self.select(row)
                return True
            if ev.kind == "up":
                if row is not None:
                    self.choose(row)
                return True
        if isinstance(ev, WheelEvent):
            self.top = max(0, min(self.top - int(ev.dy), max(0, len(self.items) - self.rows)))
            self.invalidate()
            return True
        return False


class ComboBox(Widget):
    focusable = True

    def __init__(
        self,
        items: Sequence[object] = (),
        index: int = 0,
        *,
        on_change: Callable[[int, str], None] | None = None,
        visible_rows: int = 10,
        **kw,
    ):
        super().__init__(**kw)
        self.items = [str(i) for i in items]
        self.index = max(0, min(index, len(self.items) - 1)) if self.items else -1
        self.visible_rows = visible_rows
        self.changed = Signal()
        if on_change is not None:
            self.changed.connect(on_change)
        self._popup: ListPopup | None = None

    @property
    def text(self) -> str:
        return self.items[self.index] if 0 <= self.index < len(self.items) else ""

    def set_index(self, index: int, emit: bool = True) -> None:
        if not self.items:
            return
        index = max(0, min(index, len(self.items) - 1))
        if index != self.index:
            self.index = index
            self.invalidate()
            if emit:
                self.changed.emit(index, self.text)

    def set_text(self, text: str, emit: bool = True) -> bool:
        if text in self.items:
            self.set_index(self.items.index(text), emit)
            return True
        return False

    def set_items(self, items: Sequence[object], keep_text: bool = True) -> None:
        """목록을 바꾼다 (포트 새로고침 등). 현재 글자가 새 목록에 있으면 그대로 선택한다."""
        old = self.text
        self.items = [str(i) for i in items]
        if keep_text and old in self.items:
            self.index = self.items.index(old)
        else:
            self.index = 0 if self.items else -1
        self.relayout()
        self.invalidate()

    def size_hint(self) -> SizeHint:
        w = max((str_width(i) for i in self.items), default=4) + 4
        return SizeHint(min(w, 6), 1, w, 1, max_h=1)

    @property
    def is_open(self) -> bool:
        return self._popup is not None and self._popup.is_open

    def open(self) -> None:
        app = self.app
        if app is None or not self.items or self.is_open:
            return
        popup = ListPopup(self.items, self.index, on_choose=self.set_index, visible_rows=self.visible_rows)
        popup.owner = self
        hint = popup.effective_hint()
        w = max(self.rect.w, hint.pref_w)
        h = hint.pref_h
        # 아래 공간이 모자라면 위로 연다
        y = self.rect.bottom if self.rect.bottom + h <= app.rows else self.rect.y - h
        self._popup = popup
        app.open_popup(popup, self.rect.x, y, w, h)

    def close(self) -> None:
        if self._popup is not None:
            self._popup.close()
            self._popup = None

    def paint(self, p: Painter) -> None:
        pal = self.palette
        w = self.rect.w
        if not self.enabled:
            fg, bg = pal.disabled, pal.input_bg
        elif self.focused:
            fg, bg = pal.sel_fg, pal.sel_bg
        else:
            fg, bg = pal.input_fg, pal.input_bg
        p.fill(Rect(0, 0, w, self.rect.h), " ", fg, bg)
        p.text(1, 0, truncate(self.text, max(0, w - 4)), fg, bg)
        if w >= 3:
            p.put(w - 2, 0, "▼", fg, bg)

    def on_event(self, ev: Event) -> bool:
        if isinstance(ev, MouseEvent):
            if ev.kind == "down" and ev.button == 1:
                if self.is_open:
                    self.close()
                else:
                    self.open()
                return True
            return ev.kind == "up"
        if isinstance(ev, KeyEvent):
            k = ev.key
            if (k == Key.SPACE or ev.is_enter) and not ev.mod or (ev.alt and k == Key.DOWN):
                self.open()
            elif k == Key.UP and not ev.mod:
                self.set_index(self.index - 1)
            elif k == Key.DOWN and not ev.mod:
                self.set_index(self.index + 1)
            else:
                return False
            return True
        return False
