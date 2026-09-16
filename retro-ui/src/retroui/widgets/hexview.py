"""Hex dump of a byte stream (serial RX/TX 등).

한 줄: 오프셋 + 방향(RX/TX) + 16진수 + ASCII. 방향이 바뀌면 새 줄에서 시작해서 요청/응답 순서가 보인다.
한 줄에 넣는 바이트 수는 폭에 맞춰 4/8/16 중에서 고른다 (좁으면 ASCII 칸을 뺀다).
오래된 줄은 max_rows 만큼만 남긴다: 1Mbps 로 쏟아져도 메모리가 늘지 않는다.
"""

from __future__ import annotations

from retroui.core.geometry import Rect
from retroui.core.signal import Signal
from retroui.input.events import IS_MAC, Event, Mod, MouseEvent, WheelEvent
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
        # 정지: 자동으로 최신을 따라가지 않는다. 데이터는 계속 쌓이고, 정지 중에도 스크롤로 볼 수 있다.
        # 보여줄 마지막 줄 번호를 잡아 둔다 (화면이 덜 찼을 때도 새 줄이 그려지지 않게)
        self._frozen_rows: int | None = None
        self._sealed = False  # 정지 중에는 마지막 줄에 바이트를 덧붙이지 않는다 (그 줄이 변하면 멈춘 게 아니다)
        self.wheel_lines = 1 if IS_MAC else 3
        self._wheel_accum = 0.0
        self.scrollbar = ScrollBar(on_scroll=self._on_scrollbar)
        self.add(self.scrollbar)
        # 선택은 화면 위치가 아니라 바이트 오프셋으로 기억한다: 새 데이터가 와도 같은 바이트를 가리킨다
        self.selection: tuple[int, int] | None = None
        self.selection_changed = Signal()
        self._anchor: int | None = None
        self._selecting = False

    # ---- data ----------------------------------------------------------

    def append(self, data: bytes, direction: str = "rx") -> None:
        if not data:
            return
        rows = self.rows
        per_row = self.bytes_per_row
        added = 0
        start = 0
        if rows and rows[-1][1] == direction and len(rows[-1][2]) < per_row and not self._sealed:
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
            removed = len(rows) - self.max_rows
            del rows[:removed]
            if self._frozen_rows is not None:
                self._frozen_rows = max(0, self._frozen_rows - removed)
            if self.selection and self.selection[0] < rows[0][0]:
                self.clear_selection()  # 선택한 바이트가 잘려 나갔다
        if added and self.scroll_offset and not self.paused:
            self.scroll_offset += added  # 과거를 보는 중에는 보던 자리를 유지한다 (정지 중이면 _frozen_rows 가 잡아 준다)
        self._clamp_scroll()
        self._sync_scrollbar()
        self.invalidate()

    def clear(self) -> None:
        self.rows.clear()
        self.next_offset = 0
        self.scroll_offset = 0
        self.clear_selection()
        self._sync_scrollbar()
        self.invalidate()

    def set_paused(self, paused: bool) -> None:
        if paused == self.paused:
            return
        self.paused = paused
        self._sealed = paused
        if paused:
            self._frozen_rows = len(self.rows)
        else:
            self._frozen_rows = None
            self.scroll_offset = 0  # 다시 켜면 최신으로 따라간다
        self._clamp_scroll()
        self._sync_scrollbar()
        self.invalidate()

    @property
    def shown_rows(self) -> int:
        """화면에 보여줄 줄 수 (정지 중이면 그때까지의 줄만)."""
        if self.paused and self._frozen_rows is not None:
            return min(self._frozen_rows, len(self.rows))
        return len(self.rows)

    # ---- selection -----------------------------------------------------

    def byte_at(self, cx: int, cy: int) -> int | None:
        """화면 좌표가 가리키는 바이트 오프셋 (16진수 칸과 ASCII 칸 모두). 빈 곳이면 None."""
        row = cy - self.rect.y
        index = self.view_top() + row
        if not 0 <= row < self.rect.h or index >= self.shown_rows:
            return None
        offset, _direction, data = self.rows[index]
        col = cx - self.rect.x
        hex_x = _OFFSET_W + 1 + _DIR_W + 1
        if hex_x <= col < hex_x + 3 * len(data) - 1:
            return offset + (col - hex_x) // 3
        ascii_x = hex_x + 3 * self.bytes_per_row - 1 + _ASCII_GAP
        if self.ascii_column and ascii_x <= col < ascii_x + len(data):
            return offset + col - ascii_x
        return None

    def set_selection(self, start: int, end: int) -> None:
        selection = (min(start, end), max(start, end))
        if selection != self.selection:
            self.selection = selection
            self.invalidate()
            self.selection_changed.emit()

    def clear_selection(self) -> None:
        if self.selection is not None:
            self.selection = None
            self._anchor = None
            self.invalidate()
            self.selection_changed.emit()

    def selected_bytes(self) -> bytes:
        if self.selection is None:
            return b""
        start, end = self.selection
        out = bytearray()
        for offset, _direction, data in self.rows:
            if offset + len(data) <= start or offset > end:
                continue
            lo = max(0, start - offset)
            hi = min(len(data), end - offset + 1)
            out.extend(data[lo:hi])
        return bytes(out)

    # ---- scroll --------------------------------------------------------

    @property
    def rows_visible(self) -> int:
        return max(1, self.rect.h)

    def view_top(self) -> int:
        return max(0, self.shown_rows - self.rows_visible - self.scroll_offset)

    def scroll(self, delta: int) -> None:
        """delta > 0 이면 위(과거)로. 정지 중에는 보여주는 구간 자체를 옮긴다."""
        if self.paused and self._frozen_rows is not None:
            lowest = min(self.rows_visible, len(self.rows))
            self._frozen_rows = max(lowest, min(len(self.rows), self._frozen_rows - delta))
        else:
            self.scroll_offset += delta
        self._clamp_scroll()
        self._sync_scrollbar()
        self.invalidate()

    def _clamp_scroll(self) -> None:
        self.scroll_offset = max(0, min(self.scroll_offset, max(0, self.shown_rows - self.rows_visible)))

    def _sync_scrollbar(self) -> None:
        # 손잡이 크기는 전체 데이터 기준: 정지 중에도 데이터가 쌓이면 손잡이가 작아져 눈에 보인다
        self.scrollbar.set_range(len(self.rows), self.rows_visible, self.view_top())

    def _on_scrollbar(self, pos: int) -> None:
        if self.paused and self._frozen_rows is not None:
            self._frozen_rows = max(min(self.rows_visible, len(self.rows)), min(len(self.rows), pos + self.rows_visible))
        else:
            self.scroll_offset = max(0, len(self.rows) - self.rows_visible - pos)
        self._clamp_scroll()
        self._sync_scrollbar()
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
        hex_x = _OFFSET_W + 1 + _DIR_W + 1
        ascii_x = hex_x + 3 * self.bytes_per_row - 1 + _ASCII_GAP
        selection = self.selection
        for row in range(h):
            index = top + row
            if index >= self.shown_rows:
                break
            offset, direction, data = self.rows[index]
            color = pal.accent if direction == "tx" else pal.fg
            p.text(0, row, f"{offset:08X}", pal.dim, pal.bg)
            p.text(_OFFSET_W + 1, row, "TX" if direction == "tx" else "RX", color, pal.bg)
            for i, byte in enumerate(data):
                picked = selection is not None and selection[0] <= offset + i <= selection[1]
                fg, bg = (pal.sel_fg, pal.sel_bg) if picked else (color, pal.bg)
                x = hex_x + 3 * i
                if x + 2 <= w:
                    p.text(x, row, f"{byte:02X}", fg, bg)
                if self.ascii_column and ascii_x + i < w:
                    ch = chr(byte) if 0x20 <= byte < 0x7F else "."
                    p.put(ascii_x + i, row, ch, fg, bg)

    def on_event(self, ev: Event) -> bool:
        if isinstance(ev, WheelEvent):
            self._wheel(ev.dy)
            return True
        if isinstance(ev, MouseEvent):
            # 이동 이벤트는 button 이 0 이다: 누른 뒤 끄는 중인지는 _selecting 으로 본다
            if ev.kind == "down" and ev.button == 1:
                index = self.byte_at(ev.cx, ev.cy)
                if index is None:
                    self.clear_selection()
                elif ev.mod & Mod.SHIFT and self._anchor is not None:
                    self.set_selection(self._anchor, index)  # Shift+클릭: 처음 고른 바이트부터
                else:
                    self._anchor = index
                    self.set_selection(index, index)
                self._selecting = index is not None
                return True
            if ev.kind == "move" and self._selecting and self._anchor is not None:
                index = self.byte_at(ev.cx, ev.cy)
                if index is not None:
                    self.set_selection(self._anchor, index)
                return True
            if ev.kind == "up" and ev.button == 1:
                self._selecting = False
                return True
        return False
