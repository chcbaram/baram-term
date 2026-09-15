"""Widget-local drawing API over the cell buffer (translate + clip)."""

from __future__ import annotations

from retroui.core.geometry import Rect
from retroui.core.wcwidth import str_width, truncate
from retroui.render.cellbuffer import CellBuffer
from retroui.theme import BoxStyle

RGB = tuple[int, int, int]


class Painter:
    """모든 좌표는 위젯 로컬 셀 좌표. 클립 밖으로는 절대 쓰지 않는다."""

    def __init__(self, buf: CellBuffer, origin: tuple[int, int] = (0, 0), clip: Rect | None = None):
        self.buf = buf
        self.ox, self.oy = origin
        self.clip = buf.rect if clip is None else clip.intersect(buf.rect)

    def sub(self, rect: Rect) -> Painter:
        abs_rect = rect.translate(self.ox, self.oy)
        return Painter(self.buf, (abs_rect.x, abs_rect.y), self.clip.intersect(abs_rect))

    def put(self, x: int, y: int, ch: str, fg: RGB, bg: RGB, attr: int = 0) -> int:
        return self.buf.put(x + self.ox, y + self.oy, ch, fg, bg, attr, self.clip)

    def text(self, x: int, y: int, s: str, fg: RGB, bg: RGB, attr: int = 0) -> int:
        return self.buf.text(x + self.ox, y + self.oy, s, fg, bg, attr, self.clip) - self.ox

    def fill(self, rect: Rect, ch: str = " ", fg: RGB = (0, 0, 0), bg: RGB = (0, 0, 0), attr: int = 0) -> None:
        self.buf.fill(rect.translate(self.ox, self.oy).intersect(self.clip), ch, fg, bg, attr)

    def hline(self, x: int, y: int, w: int, ch: str, fg: RGB, bg: RGB, attr: int = 0) -> None:
        self.fill(Rect(x, y, w, 1), ch, fg, bg, attr)

    def vline(self, x: int, y: int, h: int, ch: str, fg: RGB, bg: RGB, attr: int = 0) -> None:
        self.fill(Rect(x, y, 1, h), ch, fg, bg, attr)

    def box(
        self,
        rect: Rect,
        style: BoxStyle,
        fg: RGB,
        bg: RGB,
        title: str | None = None,
        title_fg: RGB | None = None,
        fill: bool = True,
        title_align: str = "left",
    ) -> None:
        if rect.w < 2 or rect.h < 2:
            return
        if fill:
            self.fill(rect.inset(1), " ", fg, bg)
        x0, y0 = rect.x, rect.y
        x1, y1 = rect.right - 1, rect.bottom - 1
        self.hline(x0 + 1, y0, rect.w - 2, style.h, fg, bg)
        self.hline(x0 + 1, y1, rect.w - 2, style.h, fg, bg)
        self.vline(x0, y0 + 1, rect.h - 2, style.v, fg, bg)
        self.vline(x1, y0 + 1, rect.h - 2, style.v, fg, bg)
        self.put(x0, y0, style.tl, fg, bg)
        self.put(x1, y0, style.tr, fg, bg)
        self.put(x0, y1, style.bl, fg, bg)
        self.put(x1, y1, style.br, fg, bg)
        if title and rect.w >= 6:
            label = truncate(title, rect.w - 6)
            span = str_width(label) + 4  # ┤ + 공백 + 제목 + 공백 + ├
            if title_align == "right":
                start = x1 - span
            elif title_align == "center":
                start = x0 + (rect.w - span) // 2
            else:
                start = x0 + 1
            self.put(start, y0, style.tee_left, fg, bg)
            end = self.text(start + 1, y0, f" {label} ", title_fg or fg, bg)
            self.put(end, y0, style.tee_right, fg, bg)

    @staticmethod
    def width_of(s: str) -> int:
        return str_width(s)
