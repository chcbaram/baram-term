"""Vertical scroll bar with 1/8-cell thumb precision.

손잡이 끝이 셀 경계에 걸리면 아래쪽 1/8 블록 문자(▁▂▃▄▅▆▇)로 채워서 셀 1/8 단위로 움직인다.
스크롤백이 수천 줄이어도 손잡이가 한 칸씩 툭툭 튀지 않게 하기 위해서다.

값: total(전체 줄 수), page(한 화면 줄 수), pos(맨 위에 보이는 줄, 0..total-page).
set_range() 는 프로그램에서 값을 맞출 때(신호 없음), scrolled(pos) 는 사용자가 움직였을 때만 나온다.
"""

from __future__ import annotations

from typing import Callable

from retroui.core.signal import Signal
from retroui.input.events import Event, MouseEvent
from retroui.render.painter import Painter
from retroui.widgets.base import SizeHint, Widget

_EIGHTHS = "▁▂▃▄▅▆▇█"  # 아래에서부터 n/8 채움


class ScrollBar(Widget):
    def __init__(self, *, on_scroll: Callable[[int], None] | None = None, **kw):
        super().__init__(**kw)
        self.total = 0
        self.page = 1
        self.pos = 0
        self.scrolled = Signal()
        if on_scroll is not None:
            self.scrolled.connect(on_scroll)
        # 손잡이 최소 길이 (1/8칸 단위). 너무 짧으면 잡기 어렵다
        self.min_thumb = 8
        self._grab: int | None = None

    @property
    def max_pos(self) -> int:
        return max(0, self.total - self.page)

    @property
    def scrollable(self) -> bool:
        return self.total > self.page

    def set_range(self, total: int, page: int, pos: int) -> None:
        total = max(0, int(total))
        page = max(1, int(page))
        pos = max(0, min(int(pos), max(0, total - page)))
        if (total, page, pos) != (self.total, self.page, self.pos):
            self.total, self.page, self.pos = total, page, pos
            self.invalidate()

    def size_hint(self) -> SizeHint:
        return SizeHint(1, 1, 1, 1, max_w=1)

    def thumb(self) -> tuple[int, int] | None:
        """손잡이 (시작, 끝) — 1/8칸 단위, 끝은 포함하지 않음. 스크롤할 게 없으면 None."""
        if not self.scrollable or self.rect.h <= 0:
            return None
        track = self.rect.h * 8
        length = min(track, max(self.min_thumb, round(track * self.page / self.total)))
        start = round((track - length) * self.pos / self.max_pos) if self.max_pos else 0
        return start, start + length

    def paint(self, p: Painter) -> None:
        pal = self.palette
        track = pal.grid
        handle = pal.border_focus if self._grab is not None or self.hovered else pal.dim
        th = self.thumb()
        for y in range(self.rect.h):
            if th is None:
                p.put(0, y, " ", pal.fg, track)
                continue
            top, bottom = y * 8, y * 8 + 8
            o0, o1 = max(top, th[0]), min(bottom, th[1])
            if o1 <= o0:
                p.put(0, y, " ", handle, track)
            elif o0 == top and o1 == bottom:
                p.put(0, y, " ", handle, handle)
            elif o0 == top:
                # 손잡이가 셀 위쪽 k/8 만 차지: 아래 (8-k)/8 을 트랙색 블록으로 덮는다
                p.put(0, y, _EIGHTHS[8 - (o1 - top) - 1], track, handle)
            else:
                # 손잡이가 셀 아래쪽 k/8 에서 시작
                p.put(0, y, _EIGHTHS[(bottom - o0) - 1], handle, track)

    def _eighth_at(self, ev: MouseEvent) -> int:
        app = self.app
        ch = app.fonts.ch if app is not None else 8
        return (ev.py - self.rect.y * ch) * 8 // ch

    def _move_to(self, pos: int) -> None:
        pos = max(0, min(pos, self.max_pos))
        if pos != self.pos:
            self.pos = pos
            self.invalidate()
            self.scrolled.emit(pos)

    def on_event(self, ev: Event) -> bool:
        if not isinstance(ev, MouseEvent):
            return False
        th = self.thumb()
        if ev.kind == "down" and ev.button == 1:
            if th is not None:
                y8 = self._eighth_at(ev)
                if th[0] <= y8 < th[1]:
                    self._grab = y8 - th[0]
                    self.invalidate()
                elif y8 < th[0]:
                    self._move_to(self.pos - self.page)
                else:
                    self._move_to(self.pos + self.page)
            return True
        if ev.kind == "move" and self._grab is not None:
            if th is not None:
                track = self.rect.h * 8
                length = th[1] - th[0]
                start = self._eighth_at(ev) - self._grab
                if track > length:
                    self._move_to(round(start * self.max_pos / (track - length)))
            return True
        if ev.kind == "up" and ev.button == 1:
            if self._grab is not None:
                self._grab = None
                self.invalidate()
            return True
        return False
