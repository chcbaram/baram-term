"""Character-cell back buffer with wide-char handling and change tracking.

와이드 문자(한글 등)는 x 셀에 글자, x+1 셀에 WIDE_CONT 를 둔다. 어느 한쪽 절반이 덮이면
나머지 절반은 공백이 되어 반쪽 글자가 화면에 남지 않는다.
"""

from __future__ import annotations

from enum import IntFlag
from typing import Iterator

from retroui.core.geometry import Rect
from retroui.core.wcwidth import char_width, normalize

RGB = tuple[int, int, int]
Cell = tuple[str, RGB, RGB, int]

WIDE_CONT = ""


class Attr(IntFlag):
    NONE = 0
    BOLD = 1
    UNDERLINE = 2
    REVERSE = 4
    DIM = 8
    PIXEL = 16  # 픽셀 위젯이 직접 그리는 셀: 셀 렌더러가 건너뛴다
    FILL = 32  # attr 상위 비트에 세 번째 색(채움색)이 실려 있다: fill_attr()/attr_fill()


def fill_attr(rgb: RGB) -> int:
    """셀 하나에 선(fg), 바깥(bg) 외에 안쪽 채움색이 더 필요할 때 attr 상위 비트에 싣는다.

    박스 버튼 테두리 셀처럼 선 안쪽만 채워야 하는 경우에 쓴다. 비트 8~31 에 RGB.
    """
    r, g, b = rgb
    return int(Attr.FILL) | (((r << 16) | (g << 8) | b) << 8)


def attr_fill(attr: int) -> RGB | None:
    if not attr & Attr.FILL:
        return None
    v = attr >> 8
    return ((v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF)


class CellBuffer:
    def __init__(self, cols: int, rows: int, fg: RGB = (170, 170, 170), bg: RGB = (0, 0, 0)):
        self.fg = fg
        self.bg = bg
        self.resize(cols, rows)

    def resize(self, cols: int, rows: int) -> None:
        self.cols = max(0, cols)
        self.rows = max(0, rows)
        blank: Cell = (" ", self.fg, self.bg, 0)
        self._back: list[list[Cell]] = [[blank] * self.cols for _ in range(self.rows)]
        self.invalidate_all()

    def invalidate_all(self) -> None:
        # front 가 None 인 행은 화면에 그려진 적이 없다고 보고 전체를 변경으로 낸다 (리사이즈, 폰트 변경 후)
        self._front: list[list[Cell] | None] = [None] * self.rows
        self._dirty: set[int] = set(range(self.rows))

    @property
    def rect(self) -> Rect:
        return Rect(0, 0, self.cols, self.rows)

    def get(self, x: int, y: int) -> Cell:
        return self._back[y][x]

    def row(self, y: int) -> list[Cell]:
        """렌더러용 행 참조. 직접 수정하지 말고 put/text/fill 을 쓴다 (변경 추적이 빠진다)."""
        return self._back[y]

    def row_text(self, y: int) -> str:
        return "".join(c[0] for c in self._back[y] if c[0] != WIDE_CONT)

    def text_lines(self) -> list[str]:
        return [self.row_text(y) for y in range(self.rows)]

    @staticmethod
    def _break_wide(row: list[Cell], x: int) -> None:
        cell = row[x]
        if cell[0] == WIDE_CONT:
            if x > 0:
                lead = row[x - 1]
                row[x - 1] = (" ", lead[1], lead[2], lead[3])
        elif x + 1 < len(row) and row[x + 1][0] == WIDE_CONT:
            tail = row[x + 1]
            row[x + 1] = (" ", tail[1], tail[2], tail[3])

    def _area(self, clip: Rect | None) -> Rect:
        return self.rect if clip is None else clip.intersect(self.rect)

    def put(self, x: int, y: int, ch: str, fg: RGB, bg: RGB, attr: int = 0, clip: Rect | None = None) -> int:
        """한 글자를 놓고 글자의 열 폭을 돌려준다 (클립 밖이어도 폭은 돌려준다)."""
        width = char_width(ch)
        if width == 0:
            return 0
        area = self._area(clip)
        if not area.contains(x, y):
            return width
        row = self._back[y]
        w = width
        if w == 2 and x + 1 >= area.right:
            ch, w = " ", 1
        self._break_wide(row, x)
        if w == 2:
            self._break_wide(row, x + 1)
        row[x] = (ch, fg, bg, attr)
        if w == 2:
            row[x + 1] = (WIDE_CONT, fg, bg, attr)
        self._dirty.add(y)
        return width

    def text(self, x: int, y: int, s: str, fg: RGB, bg: RGB, attr: int = 0, clip: Rect | None = None) -> int:
        """문자열을 쓰고 마지막 글자 다음 열을 돌려준다 (클립 오른쪽 끝에서 멈춘다)."""
        area = self._area(clip)
        if not (area.y <= y < area.bottom):
            return x
        for ch in normalize(s):
            w = char_width(ch)
            if w == 0:
                continue
            if x >= area.right:
                break
            if x < area.x:
                if x + w > area.x:
                    self.put(area.x, y, " ", fg, bg, attr, area)
            else:
                self.put(x, y, ch, fg, bg, attr, area)
            x += w
        return x

    def fill(self, rect: Rect, ch: str, fg: RGB, bg: RGB, attr: int = 0) -> None:
        area = rect.intersect(self.rect)
        if area.empty:
            return
        if char_width(ch) != 1:
            ch = " "
        cell: Cell = (ch, fg, bg, attr)
        for y in range(area.y, area.bottom):
            row = self._back[y]
            self._break_wide(row, area.x)
            self._break_wide(row, area.right - 1)
            row[area.x : area.right] = [cell] * area.w
            self._dirty.add(y)

    def changed_runs(self) -> Iterator[tuple[int, int, int]]:
        """마지막 commit 이후 바뀐 (row, x0, x1) 구간. 와이드 문자 쌍은 쪼개지 않는다."""
        n = self.cols
        for y in sorted(self._dirty):
            back = self._back[y]
            front = self._front[y]
            if front is None:
                if n:
                    yield (y, 0, n)
                continue
            x = 0
            while x < n:
                if back[x] == front[x]:
                    x += 1
                    continue
                x0 = x
                while x < n and back[x] != front[x]:
                    x += 1
                x1 = x
                if x0 > 0 and back[x0][0] == WIDE_CONT:
                    x0 -= 1
                if x1 < n and back[x1][0] == WIDE_CONT:
                    x1 += 1
                yield (y, x0, x1)

    def commit(self) -> None:
        for y in self._dirty:
            self._front[y] = list(self._back[y])
        self._dirty.clear()
