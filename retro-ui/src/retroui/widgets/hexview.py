"""Hex dump of a byte stream (serial RX/TX 등).

한 줄: 오프셋 + 방향(RX/TX) + 16진수 + ASCII. 방향이 바뀌면 새 줄에서 시작해서 요청/응답 순서가 보인다.
한 줄에 넣는 바이트 수는 폭에 맞춰 4/8/16 중에서 고른다 (좁으면 ASCII 칸을 뺀다).
오래된 줄은 max_rows 만큼만 남긴다: 1Mbps 로 쏟아져도 메모리가 늘지 않는다.
"""

from __future__ import annotations

from retroui.core.geometry import Rect
from retroui.core.wcwidth import truncate
from retroui.input.events import IS_MAC, Event, WheelEvent
from retroui.render.painter import Painter
from retroui.widgets.base import SizeHint, Widget
from retroui.widgets.scrollbar import ScrollBar

_OFFSET_W = 8
_DIR_W = 2
_ASCII_GAP = 2
_SIZES = (16, 8, 4)


def row_width(n: int, ascii_column: bool) -> int:
    """한 줄에 n 바이트를 넣을 때 필요한 칸 수 (스크롤바 제외)."""
    width = _OFFSET_W + 1 + _DIR_W + 1 + (3 * n - 1)
    return width + (_ASCII_GAP + n if ascii_column else 0)


class HexView(Widget):
    def __init__(self, *, max_rows: int = 5000, stretch: int = 1, **kw):
        super().__init__(stretch=stretch, **kw)
        # (오프셋, 방향, 바이트). 방향은 "rx" | "tx"
        self.rows: list[tuple[int, str, bytearray]] = []
        self.next_offset = 0
        self.max_rows = max_rows
        self.trim_slack = 256  # 줄마다 앞을 지우지 않고 한 번에 모아서 지운다
        self.bytes_per_row = 8
        self.ascii_column = True
        self.scroll_offset = 0  # 0 이면 맨 아래(최신)
        self.paused = False
        self.wheel_lines = 1 if IS_MAC else 3
        self._wheel_accum = 0.0
        self.scrollbar = ScrollBar(on_scroll=self._on_scrollbar)
        self.add(self.scrollbar)

    # ---- data ----------------------------------------------------------

    def append(self, data: bytes, direction: str = "rx") -> None:
        if not data:
            return
        rows = self.rows
        per_row = self.bytes_per_row
        added = 0
        start = 0
        if rows and rows[-1][1] == direction and len(rows[-1][2]) < per_row:
            take = min(per_row - len(rows[-1][2]), len(data))
            rows[-1][2].extend(data[:take])
            start = take
        while start < len(data):
            take = min(per_row, len(data) - start)
            rows.append((self.next_offset + start, direction, bytearray(data[start : start + take])))
            added += 1
            start += take
        self.next_offset += len(data)
        if len(rows) > self.max_rows + self.trim_slack:
            del rows[: len(rows) - self.max_rows]
        if added and (self.paused or self.scroll_offset):
            self.scroll_offset += added  # 과거를 보는 중(또는 정지)에는 보던 자리를 유지한다
        self._clamp_scroll()
        self._sync_scrollbar()
        self.invalidate()

    def clear(self) -> None:
        self.rows.clear()
        self.next_offset = 0
        self.scroll_offset = 0
        self._sync_scrollbar()
        self.invalidate()

    def set_paused(self, paused: bool) -> None:
        if paused == self.paused:
            return
        self.paused = paused
        if not paused:
            self.scroll_offset = 0  # 다시 켜면 최신으로 따라간다
            self._sync_scrollbar()
        self.invalidate()

    # ---- scroll --------------------------------------------------------

    @property
    def rows_visible(self) -> int:
        return max(1, self.rect.h)

    def view_top(self) -> int:
        return max(0, len(self.rows) - self.rows_visible - self.scroll_offset)

    def scroll(self, delta: int) -> None:
        self.scroll_offset += delta
        self._clamp_scroll()
        self._sync_scrollbar()
        self.invalidate()

    def _clamp_scroll(self) -> None:
        self.scroll_offset = max(0, min(self.scroll_offset, max(0, len(self.rows) - self.rows_visible)))

    def _sync_scrollbar(self) -> None:
        total = len(self.rows)
        page = self.rows_visible
        self.scrollbar.set_range(total, page, max(0, total - page - self.scroll_offset))

    def _on_scrollbar(self, pos: int) -> None:
        self.scroll_offset = max(0, len(self.rows) - self.rows_visible - pos)
        self._clamp_scroll()
        self.invalidate()

    def _wheel(self, dy: float) -> None:
        # 터미널과 같은 방식: wheel_lines 를 곱하고 남는 소수는 다음 이벤트로 넘긴다
        self._wheel_accum += dy * self.wheel_lines
        lines = int(self._wheel_accum + (1e-6 if self._wheel_accum > 0 else -1e-6))
        self._wheel_accum -= lines
        if lines:
            self.scroll(lines)

    # ---- layout / paint ------------------------------------------------

    def size_hint(self) -> SizeHint:
        return SizeHint(row_width(4, False) + 1, 3, row_width(8, True) + 1, 12)

    def fit(self, width: int) -> tuple[int, bool]:
        """폭에 맞는 (한 줄 바이트 수, ASCII 칸 표시 여부)."""
        content = max(0, width - 1)  # 오른쪽 스크롤바
        for n in _SIZES:
            if row_width(n, True) <= content:
                return n, True
        for n in _SIZES:
            if row_width(n, False) <= content:
                return n, False
        return 4, False

    def set_bytes_per_row(self, n: int, ascii_column: bool = True) -> None:
        self.ascii_column = ascii_column
        if n == self.bytes_per_row:
            return
        # 줄을 다시 나눈다: 이어진 같은 방향 줄을 합친 뒤 새 길이로 자른다
        runs: list[list] = []
        for offset, direction, data in self.rows:
            if runs and runs[-1][1] == direction and runs[-1][0] + len(runs[-1][2]) == offset:
                runs[-1][2].extend(data)
            else:
                runs.append([offset, direction, bytearray(data)])
        self.bytes_per_row = n
        self.rows = [
            (offset + i, direction, bytearray(data[i : i + n]))
            for offset, direction, data in runs
            for i in range(0, len(data), n)
        ]
        self._clamp_scroll()
        self._sync_scrollbar()
        self.invalidate()

    def _do_layout(self, rect: Rect) -> None:
        super()._do_layout(rect)
        self.set_bytes_per_row(*self.fit(rect.w))
        self._clamp_scroll()
        self._sync_scrollbar()

    def layout_children(self) -> None:
        self.scrollbar._do_layout(Rect(self.rect.right - 1, self.rect.y, 1, self.rect.h))

    def paint(self, p: Painter) -> None:
        pal = self.palette
        w = max(0, self.rect.w - 1)
        h = self.rect.h
        p.fill(Rect(0, 0, self.rect.w, h), " ", pal.fg, pal.bg)
        top = self.view_top()
        ascii_x = _OFFSET_W + 1 + _DIR_W + 1 + (3 * self.bytes_per_row - 1) + _ASCII_GAP
        for row in range(h):
            index = top + row
            if index >= len(self.rows):
                break
            offset, direction, data = self.rows[index]
            color = pal.accent if direction == "tx" else pal.fg
            p.text(0, row, f"{offset:08X}", pal.dim, pal.bg)
            p.text(_OFFSET_W + 1, row, "TX" if direction == "tx" else "RX", color, pal.bg)
            hex_text = " ".join(f"{b:02X}" for b in data)
            p.text(_OFFSET_W + 1 + _DIR_W + 1, row, truncate(hex_text, max(0, w - _OFFSET_W - 4)), color, pal.bg)
            if self.ascii_column and ascii_x < w:
                text = "".join(chr(b) if 0x20 <= b < 0x7F else "." for b in data)
                p.text(ascii_x, row, truncate(text, w - ascii_x), color, pal.bg)

    def on_event(self, ev: Event) -> bool:
        if isinstance(ev, WheelEvent):
            self._wheel(ev.dy)
            return True
        return False
