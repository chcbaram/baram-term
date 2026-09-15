"""Draw changed cells of a CellBuffer onto a pygame surface."""

from __future__ import annotations

import pygame

from retroui.render import boxdraw
from retroui.render.cellbuffer import WIDE_CONT, Attr, Cell, CellBuffer, attr_fill
from retroui.render.fonts import FontSet

RGB = tuple[int, int, int]


def _mix(a: RGB, b: RGB) -> RGB:
    return ((a[0] + b[0]) // 2, (a[1] + b[1]) // 2, (a[2] + b[2]) // 2)


class Renderer:
    def __init__(self, fonts: FontSet, buf: CellBuffer):
        self.fonts = fonts
        self.buf = buf
        # 격자를 그리기 시작하는 픽셀 위치 (창 여백 + 셀로 나누고 남은 자투리의 절반)
        self.ox = 0
        self.oy = 0

    def grid_size(self, px_w: int, px_h: int) -> tuple[int, int]:
        return max(1, px_w // self.fonts.cw), max(1, px_h // self.fonts.ch)

    def cell_rect(self, x: int, y: int, w: int = 1, h: int = 1) -> pygame.Rect:
        cw, ch = self.fonts.cw, self.fonts.ch
        return pygame.Rect(self.ox + x * cw, self.oy + y * ch, w * cw, h * ch)

    def draw_cell(self, surface: pygame.Surface, x: int, y: int, cell: Cell, width: int) -> None:
        ch, fg, bg, attr = cell
        if attr & Attr.REVERSE:
            fg, bg = bg, fg
        if attr & Attr.DIM:
            fg = _mix(fg, bg)
        rect = self.cell_rect(x, y, width)
        if attr & Attr.PIXEL:
            return
        surface.fill(bg, rect)
        if ch != " ":
            if width == 1 and boxdraw.handles(ch):
                boxdraw.draw(surface, rect, ch, fg, bg, self.fonts.scale, attr_fill(attr))
            else:
                surface.blit(self.fonts.glyph(ch, fg, bool(attr & Attr.BOLD), width), rect.topleft)
        if attr & Attr.UNDERLINE:
            t = max(1, round(self.fonts.scale))
            surface.fill(fg, (rect.x, rect.bottom - t, rect.w, t))

    def render(self, surface: pygame.Surface) -> list[pygame.Rect]:
        """마지막 render 이후 바뀐 셀만 그리고, 갱신된 픽셀 영역 목록을 돌려준다."""
        buf = self.buf
        dirty: list[pygame.Rect] = []
        for y, x0, x1 in buf.changed_runs():
            row = buf.row(y)
            x = x0
            while x < x1:
                cell = row[x]
                if cell[0] == WIDE_CONT:
                    x += 1
                    continue
                width = 2 if x + 1 < buf.cols and row[x + 1][0] == WIDE_CONT else 1
                self.draw_cell(surface, x, y, cell, width)
                x += width
            dirty.append(self.cell_rect(x0, y, x1 - x0))
        buf.commit()
        return dirty
