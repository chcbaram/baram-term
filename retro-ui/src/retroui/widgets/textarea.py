"""Multi-line text editor (메모, 스크립트 편집).

- 줄바꿈은 자동으로 하지 않는다: 긴 줄은 좌우로 스크롤한다 (명령 한 줄이 두 줄로 보이면 헷갈린다).
- 선택은 (줄, 글자) 두 지점으로 기억한다. 마우스 드래그와 Shift+이동키 모두 같은 방식이다.
- 한글 입력(IME) 조합은 커서 자리에 밑줄로 보여주고, 확정되면 그 자리에 들어간다.
- 실행 취소와 찾기는 아직 없다.
"""

from __future__ import annotations

from typing import Callable

from retroui.core.geometry import Rect
from retroui.core.signal import Signal
from retroui.core.wcwidth import char_width, normalize, str_width
from retroui.input.events import (
    CompositionEvent,
    Event,
    FocusEvent,
    Key,
    KeyEvent,
    Mod,
    MouseEvent,
    TextEvent,
    WheelEvent,
)
from retroui.render.cellbuffer import Attr
from retroui.render.painter import Painter
from retroui.widgets.base import SizeHint, Widget
from retroui.widgets.lineedit import clipboard_get, clipboard_put
from retroui.widgets.scrollbar import ScrollBar

Pos = tuple[int, int]  # (줄, 글자 인덱스)


class TextArea(Widget):
    focusable = True
    wants_text_input = True

    def __init__(
        self,
        text: str = "",
        *,
        on_change: Callable[[str], None] | None = None,
        wheel_lines: int = 3,
        stretch: int = 1,
        **kw,
    ):
        super().__init__(stretch=stretch, **kw)
        self.lines: list[str] = ["" ]
        self.row = 0
        self.col = 0
        self.anchor: Pos | None = None
        self.preedit = ""
        self.scroll_row = 0
        self.scroll_col = 0
        # 보내는 중인 줄처럼 잠깐 표시할 줄 (None 이면 없음)
        self.marked_row: int | None = None
        self.changed = Signal()  # str: 전체 글자
        if on_change is not None:
            self.changed.connect(on_change)
        self.wheel_lines = wheel_lines
        self._wheel_accum = 0.0
        self._selecting = False
        self.scrollbar = ScrollBar(on_scroll=self._on_scrollbar)
        self.add(self.scrollbar)
        self.set_text(text, emit=False)

    # ---- content -------------------------------------------------------

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    def set_text(self, text: str, emit: bool = True) -> None:
        self.lines = normalize(str(text)).replace("\r\n", "\n").replace("\r", "\n").split("\n") or [""]
        self.row = min(self.row, len(self.lines) - 1)
        self.col = min(self.col, len(self.lines[self.row]))
        self.anchor = None
        self.preedit = ""
        self._after_change(emit)

    def line(self, row: int) -> str:
        return self.lines[row] if 0 <= row < len(self.lines) else ""

    @property
    def line_count(self) -> int:
        return len(self.lines)

    def _after_change(self, emit: bool = True) -> None:
        self._scroll_to_cursor()
        self._sync_scrollbar()
        self.invalidate()
        if emit:
            self.changed.emit(self.text)

    # ---- selection -----------------------------------------------------

    def selection(self) -> tuple[Pos, Pos] | None:
        """정렬된 (시작, 끝). 선택이 없으면 None."""
        if self.anchor is None or self.anchor == (self.row, self.col):
            return None
        return tuple(sorted((self.anchor, (self.row, self.col))))  # type: ignore[return-value]

    def selected_text(self) -> str:
        span = self.selection()
        if span is None:
            return ""
        (r0, c0), (r1, c1) = span
        if r0 == r1:
            return self.lines[r0][c0:c1]
        parts = [self.lines[r0][c0:], *self.lines[r0 + 1 : r1], self.lines[r1][:c1]]
        return "\n".join(parts)

    def selected_rows(self) -> tuple[int, int] | None:
        """선택에 걸친 줄 범위 (끝 줄 포함). 줄 중간만 골라도 그 줄 전체를 센다."""
        span = self.selection()
        if span is None:
            return None
        (r0, _c0), (r1, c1) = span
        if r1 > r0 and c1 == 0:
            r1 -= 1  # 다음 줄 첫 칸에서 끝나면 그 줄은 고르지 않은 것으로
        return r0, max(r0, r1)

    def select_all(self) -> None:
        self.anchor = (0, 0)
        self.row = len(self.lines) - 1
        self.col = len(self.lines[self.row])
        self._after_change(emit=False)

    def clear_selection(self) -> None:
        if self.anchor is not None:
            self.anchor = None
            self.invalidate()

    # ---- editing -------------------------------------------------------

    def _delete_selection(self) -> bool:
        span = self.selection()
        if span is None:
            return False
        (r0, c0), (r1, c1) = span
        self.lines[r0 : r1 + 1] = [self.lines[r0][:c0] + self.lines[r1][c1:]]
        self.row, self.col = r0, c0
        self.anchor = None
        return True

    def insert(self, text: str) -> None:
        text = normalize(text).replace("\r\n", "\n").replace("\r", "\n")
        text = "".join(ch for ch in text if ch >= " " or ch == "\n")
        self._delete_selection()
        line = self.lines[self.row]
        head, tail = line[: self.col], line[self.col :]
        parts = text.split("\n")
        if len(parts) == 1:
            self.lines[self.row] = head + parts[0] + tail
            self.col += len(parts[0])
        else:
            block = [head + parts[0], *parts[1:-1], parts[-1] + tail]
            self.lines[self.row : self.row + 1] = block
            self.row += len(parts) - 1
            self.col = len(parts[-1])
        self._after_change()

    def backspace(self) -> None:
        if self._delete_selection():
            self._after_change()
            return
        if self.col > 0:
            line = self.lines[self.row]
            self.lines[self.row] = line[: self.col - 1] + line[self.col :]
            self.col -= 1
        elif self.row > 0:
            above = self.lines[self.row - 1]
            self.lines[self.row - 1] = above + self.lines[self.row]
            del self.lines[self.row]
            self.row -= 1
            self.col = len(above)
        else:
            return
        self._after_change()

    def delete(self) -> None:
        if self._delete_selection():
            self._after_change()
            return
        line = self.lines[self.row]
        if self.col < len(line):
            self.lines[self.row] = line[: self.col] + line[self.col + 1 :]
        elif self.row + 1 < len(self.lines):
            self.lines[self.row] = line + self.lines[self.row + 1]
            del self.lines[self.row + 1]
        else:
            return
        self._after_change()

    # ---- cursor --------------------------------------------------------

    def move_to(self, row: int, col: int, extend: bool = False) -> None:
        if extend:
            if self.anchor is None:
                self.anchor = (self.row, self.col)
        else:
            self.anchor = None
        self.row = max(0, min(row, len(self.lines) - 1))
        self.col = max(0, min(col, len(self.lines[self.row])))
        self._scroll_to_cursor()
        self._sync_scrollbar()
        self.invalidate()

    def _move_horizontal(self, delta: int, extend: bool) -> None:
        row, col = self.row, self.col + delta
        if col < 0:
            if row == 0:
                col = 0
            else:
                row -= 1
                col = len(self.lines[row])
        elif col > len(self.lines[row]):
            if row + 1 < len(self.lines):
                row += 1
                col = 0
            else:
                col = len(self.lines[row])
        self.move_to(row, col, extend)

    # ---- scroll --------------------------------------------------------

    @property
    def rows_visible(self) -> int:
        return max(1, self.rect.h)

    @property
    def content_width(self) -> int:
        return max(1, self.rect.w - 1)  # 오른쪽 스크롤바

    def _col_x(self, row: int, col: int) -> int:
        return str_width(self.lines[row][:col])

    def _scroll_to_cursor(self) -> None:
        self.scroll_row = max(0, min(self.scroll_row, max(0, len(self.lines) - self.rows_visible)))
        if self.row < self.scroll_row:
            self.scroll_row = self.row
        elif self.row >= self.scroll_row + self.rows_visible:
            self.scroll_row = self.row - self.rows_visible + 1
        x = self._col_x(self.row, self.col) + str_width(self.preedit)
        if x < self.scroll_col:
            self.scroll_col = x
        elif x >= self.scroll_col + self.content_width:
            self.scroll_col = x - self.content_width + 1

    def scroll(self, delta: int) -> None:
        """delta > 0 이면 위로."""
        top = max(0, min(self.scroll_row - delta, max(0, len(self.lines) - self.rows_visible)))
        if top != self.scroll_row:
            self.scroll_row = top
            self._sync_scrollbar()
            self.invalidate()

    def _sync_scrollbar(self) -> None:
        self.scrollbar.set_range(len(self.lines), self.rows_visible, self.scroll_row)

    def _on_scrollbar(self, pos: int) -> None:
        self.scroll_row = max(0, min(pos, max(0, len(self.lines) - self.rows_visible)))
        self.invalidate()

    def _wheel(self, dy: float) -> None:
        self._wheel_accum += dy * self.wheel_lines
        lines = int(self._wheel_accum + (1e-6 if self._wheel_accum > 0 else -1e-6))
        self._wheel_accum -= lines
        if lines:
            self.scroll(lines)

    # ---- layout / paint ------------------------------------------------

    def size_hint(self) -> SizeHint:
        return SizeHint(12, 3, 40, 10)

    def _do_layout(self, rect: Rect) -> None:
        super()._do_layout(rect)
        self._scroll_to_cursor()
        self._sync_scrollbar()

    def layout_children(self) -> None:
        self.scrollbar._do_layout(Rect(self.rect.right - 1, self.rect.y, 1, self.rect.h))

    def pos_at(self, cx: int, cy: int) -> Pos:
        """화면 좌표 → (줄, 글자). 와이드 문자는 절반을 넘으면 다음 글자."""
        row = max(0, min(self.scroll_row + (cy - self.rect.y), len(self.lines) - 1))
        target = cx - self.rect.x + self.scroll_col
        line = self.lines[row]
        x = 0
        for i, ch in enumerate(line):
            w = char_width(ch)
            if target < x + max(1, w) / 2:
                return row, i
            x += w
        return row, len(line)

    def _in_selection(self, span: tuple[Pos, Pos], row: int, col: int) -> bool:
        return span[0] <= (row, col) < span[1]

    def paint(self, p: Painter) -> None:
        pal = self.palette
        w = self.content_width
        h = self.rect.h
        p.fill(Rect(0, 0, self.rect.w, h), " ", pal.input_fg, pal.input_bg)
        span = self.selection()
        for y in range(h):
            row = self.scroll_row + y
            if row >= len(self.lines):
                break
            line = self.lines[row]
            preedit = self.preedit if row == self.row else ""
            display = line[: self.col] + preedit + line[self.col :] if preedit else line
            row_bg = pal.hover_bg if row == self.marked_row else pal.input_bg
            if row == self.marked_row:
                p.fill(Rect(0, y, w, 1), " ", pal.input_fg, row_bg)
            x = -self.scroll_col
            for i, ch in enumerate(display):
                cw = char_width(ch)
                if x >= w:
                    break
                if x >= 0 and cw:
                    fg, bg, attr = pal.input_fg, row_bg, 0
                    if preedit and self.col <= i < self.col + len(preedit):
                        fg, attr = pal.accent, Attr.UNDERLINE
                    elif span is not None and self._in_selection(span, row, i - len(preedit) if preedit and i >= self.col else i):
                        fg, bg = pal.sel_fg, pal.sel_bg
                    p.put(x, y, ch, fg, bg, attr)
                x += cw
        if self.scroll_col:
            # 왼쪽이 잘려 있다는 표시: 앞부분이 안 보이는데 그냥 두면 다른 글로 읽힌다
            for y in range(min(h, len(self.lines) - self.scroll_row)):
                p.put(0, y, "‹", pal.dim, pal.input_bg)
        if self.focused:
            cy = self.row - self.scroll_row
            cx = self._col_x(self.row, self.col) + str_width(self.preedit) - self.scroll_col
            if 0 <= cy < h and 0 <= cx < w:
                line = self.lines[self.row]
                ch = line[self.col] if self.col < len(line) and not self.preedit else " "
                p.put(cx, cy, ch, pal.input_fg, pal.input_bg, Attr.REVERSE)

    # ---- events --------------------------------------------------------

    def on_event(self, ev: Event) -> bool:
        if isinstance(ev, TextEvent):
            self.preedit = ""
            self.insert(ev.text)
            return True
        if isinstance(ev, CompositionEvent):
            self.preedit = ev.text
            self._after_change(emit=False)
            return True
        if isinstance(ev, KeyEvent):
            return self._on_key(ev)
        if isinstance(ev, WheelEvent):
            self._wheel(ev.dy)
            return True
        if isinstance(ev, MouseEvent):
            return self._on_mouse(ev)
        if isinstance(ev, FocusEvent):
            self._selecting = False
            self.invalidate()
        return False

    def _on_key(self, ev: KeyEvent) -> bool:
        k = ev.key
        shift = ev.shift
        if ev.primary and k == Key.C:
            if self.selection():
                clipboard_put(self.selected_text())
        elif ev.primary and k == Key.X:
            if self.selection():
                clipboard_put(self.selected_text())
                self.backspace()
        elif ev.primary and k == Key.V:
            self.insert(clipboard_get())
        elif ev.primary and k == Key.A:
            self.select_all()
        elif ev.mod & (Mod.CTRL | Mod.META | Mod.ALT):
            return False  # 그 밖의 조합키는 앱으로 (보내기 단축키 등)
        elif k == Key.LEFT:
            self._move_horizontal(-1, shift)
        elif k == Key.RIGHT:
            self._move_horizontal(+1, shift)
        elif k == Key.UP:
            self.move_to(self.row - 1, self.col, shift)
        elif k == Key.DOWN:
            self.move_to(self.row + 1, self.col, shift)
        elif k == Key.HOME:
            self.move_to(self.row, 0, shift)
        elif k == Key.END:
            self.move_to(self.row, len(self.lines[self.row]), shift)
        elif k == Key.PAGEUP:
            self.move_to(self.row - self.rows_visible, self.col, shift)
        elif k == Key.PAGEDOWN:
            self.move_to(self.row + self.rows_visible, self.col, shift)
        elif k == Key.BACKSPACE:
            self.backspace()
        elif k == Key.DELETE:
            self.delete()
        elif ev.is_enter:
            self.insert("\n")
        elif k == Key.TAB:
            return False  # 포커스 이동은 앱에 맡긴다
        else:
            return False
        return True

    def _on_mouse(self, ev: MouseEvent) -> bool:
        if ev.kind == "down" and ev.button == 1:
            row, col = self.pos_at(ev.cx, ev.cy)
            self.move_to(row, col, extend=bool(ev.mod & Mod.SHIFT))
            if not ev.mod & Mod.SHIFT:
                self.anchor = (row, col)
            self._selecting = True
            return True
        if ev.kind == "move" and self._selecting:
            row, col = self.pos_at(ev.cx, ev.cy)
            self.row, self.col = row, col
            self._scroll_to_cursor()
            self.invalidate()
            return True
        if ev.kind == "up" and ev.button == 1:
            self._selecting = False
            if self.anchor == (self.row, self.col):
                self.anchor = None  # 끌지 않은 클릭은 선택 없음
            return True
        return False
