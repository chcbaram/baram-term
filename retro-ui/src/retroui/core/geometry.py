"""Integer rectangle shared by cell and pixel coordinates."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Rect:
    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0

    @property
    def right(self) -> int:
        return self.x + self.w

    @property
    def bottom(self) -> int:
        return self.y + self.h

    @property
    def empty(self) -> bool:
        return self.w <= 0 or self.h <= 0

    def contains(self, x: int, y: int) -> bool:
        return self.x <= x < self.right and self.y <= y < self.bottom

    def intersect(self, other: Rect) -> Rect:
        x0 = max(self.x, other.x)
        y0 = max(self.y, other.y)
        x1 = min(self.right, other.right)
        y1 = min(self.bottom, other.bottom)
        if x1 <= x0 or y1 <= y0:
            return Rect(x0, y0, 0, 0)
        return Rect(x0, y0, x1 - x0, y1 - y0)

    def intersects(self, other: Rect) -> bool:
        return not self.intersect(other).empty

    def union(self, other: Rect) -> Rect:
        if self.empty:
            return other
        if other.empty:
            return self
        x0 = min(self.x, other.x)
        y0 = min(self.y, other.y)
        return Rect(x0, y0, max(self.right, other.right) - x0, max(self.bottom, other.bottom) - y0)

    def translate(self, dx: int, dy: int) -> Rect:
        return Rect(self.x + dx, self.y + dy, self.w, self.h)

    def inset(self, left: int, top: int | None = None, right: int | None = None, bottom: int | None = None) -> Rect:
        top = left if top is None else top
        right = left if right is None else right
        bottom = top if bottom is None else bottom
        return Rect(self.x + left, self.y + top, max(0, self.w - left - right), max(0, self.h - top - bottom))

    def subtract(self, other: Rect) -> list[Rect]:
        """self 에서 other 를 뺀 영역을 겹치지 않는 최대 4개 사각형으로 돌려준다.

        팝업 레이어 아래의 픽셀 위젯이 팝업을 덮어 그리지 않도록 합성 영역을 자를 때 쓴다.
        """
        if self.empty:
            return []
        inter = self.intersect(other)
        if inter.empty:
            return [self]
        out = []
        if inter.y > self.y:
            out.append(Rect(self.x, self.y, self.w, inter.y - self.y))
        if inter.bottom < self.bottom:
            out.append(Rect(self.x, inter.bottom, self.w, self.bottom - inter.bottom))
        if inter.x > self.x:
            out.append(Rect(self.x, inter.y, inter.x - self.x, inter.h))
        if inter.right < self.right:
            out.append(Rect(inter.right, inter.y, self.right - inter.right, inter.h))
        return out
