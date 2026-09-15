"""Terminal widget: VT100 subset screen with scrollback.

펌웨어 CLI 콘솔을 기준으로 필요한 만큼만 구현한다 (전체 VT102 에뮬레이터가 아니다).
처리하는 것: CR/LF/BS/TAB, CSI A B C D G H f J K P @ X m s u, ESC[4h/4l(삽입 모드), ESC[?25h/l(커서),
ESC 7/8, OSC 무시, 여러 번에 나눠 들어온 ESC 시퀀스. 모르는 시퀀스는 조용히 건너뛴다.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Callable

from retroui.core.geometry import Rect
from retroui.core.signal import Signal
from retroui.core.wcwidth import char_width
from retroui.input.events import (
    CompositionEvent,
    Event,
    Key,
    KeyEvent,
    Mod,
    MouseEvent,
    TextEvent,
    WheelEvent,
)
from retroui.render.cellbuffer import Attr
from retroui.render.painter import Painter
from retroui.theme import (
    BLACK, BLUE, BROWN, CYAN, DARK_GRAY, GREEN, LIGHT_BLUE, LIGHT_CYAN, LIGHT_GRAY, LIGHT_GREEN,
    LIGHT_MAGENTA, LIGHT_RED, MAGENTA, RED, WHITE, YELLOW,
)
from retroui.widgets.base import RGB, SizeHint, Widget
from retroui.widgets.lineedit import clipboard_get

# ---- screen model ----------------------------------------------------------

WIDE_CONT = ""

# 스타일: (fg, bg, flags). fg/bg 는 None(기본색), ANSI 색 번호 0..15, 또는 (r, g, b)
BOLD = 1
UNDERLINE = 2
REVERSE = 4
DEFAULT_STYLE: tuple[int | None, int | None, int] = (None, None, 0)
BLANK = (" ", DEFAULT_STYLE)

ANSI_COLORS: tuple[RGB, ...] = (
    BLACK, RED, GREEN, BROWN, BLUE, MAGENTA, CYAN, LIGHT_GRAY,
    DARK_GRAY, LIGHT_RED, LIGHT_GREEN, YELLOW, LIGHT_BLUE, LIGHT_MAGENTA, LIGHT_CYAN, WHITE,
)

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_CSI = re.compile(r"\x1b\[([?]?)([0-9;]*)([@-~])")
_CSI_PARTIAL = re.compile(r"\x1b\[[?]?[0-9;]*")
# 스크롤백 한도를 넘으면 한 줄씩이 아니라 이만큼 모아서 지운다 (리스트 앞 삭제 비용 분산)
_TRIM_SLACK = 256


def _xterm256(n: int) -> int | tuple[int, int, int]:
    """256색 번호 -> 0..15 는 ANSI 색 번호 그대로, 나머지는 RGB."""
    n = max(0, min(255, n))
    if n < 16:
        return n
    if n >= 232:
        v = 8 + 10 * (n - 232)
        return (v, v, v)
    n -= 16
    levels = (0, 95, 135, 175, 215, 255)
    return (levels[n // 36], levels[(n // 6) % 6], levels[n % 6])


class TerminalScreen:
    """줄 목록(스크롤백 포함) + 커서. cy 는 lines 의 절대 인덱스이고, 화면은 마지막 rows 줄이다."""

    def __init__(
        self,
        cols: int = 80,
        rows: int = 24,
        max_lines: int = 5000,
        *,
        lf_implies_cr: bool = True,
        clock: Callable[[], float] = time.time,
    ):
        self.cols = max(1, cols)
        self.rows = max(1, rows)
        self.max_lines = max_lines
        # 펌웨어 로그는 \r 없이 \n 만 보내는 경우가 있어(logPrintf("\n")) 기본으로 줄 처음으로 보낸다
        self.lf_implies_cr = lf_implies_cr
        self.clock = clock
        self.wrap = True
        self.reset()

    def reset(self) -> None:
        self.lines: list[list[tuple[str, tuple]]] = [[]]
        self.stamps: list[float] = [self.clock()]
        self.cx = 0
        self.cy = 0
        self.style = DEFAULT_STYLE
        self.cursor_visible = True
        self.insert_mode = False
        self._saved = (0, 0)
        self._pending = ""
        self.dropped = 0  # 스크롤백 한도로 앞에서 지운 줄 수 누적 (스크롤 위치 고정에 쓴다)
        self.version = 0

    @property
    def top(self) -> int:
        return max(0, len(self.lines) - self.rows)

    def resize(self, cols: int, rows: int) -> None:
        self.cols = max(1, cols)
        self.rows = max(1, rows)
        self.cx = min(self.cx, self.cols)

    def line_text(self, index: int) -> str:
        return "".join(ch for ch, _ in self.lines[index] if ch != WIDE_CONT).rstrip()

    def clear(self) -> None:
        stamps_keep = self.clock()
        self.lines = [[]]
        self.stamps = [stamps_keep]
        self.cx = self.cy = 0
        self.version += 1

    # ---- input ---------------------------------------------------------

    def feed(self, text: str) -> None:
        if not text:
            return
        self.version += 1
        if self._pending:
            text = self._pending + text
            self._pending = ""
        i = 0
        n = len(text)
        while i < n:
            ch = text[i]
            if ch == "\x1b":
                used = self._escape(text, i)
                if used == 0:
                    self._pending = text[i:]  # 시퀀스가 다음 수신 조각으로 이어진다
                    break
                i += used
            elif ch < " " or ch == "\x7f":
                self._control(ch)
                i += 1
            else:
                m = _CONTROL.search(text, i)
                j = m.start() if m else n
                if "\x1b" in text[i:j]:
                    j = text.index("\x1b", i)
                self._print(text[i:j])
                i = j
        self._trim()

    def _escape(self, text: str, i: int) -> int:
        if i + 1 >= len(text):
            return 0
        nxt = text[i + 1]
        if nxt == "[":
            m = _CSI.match(text, i)
            if m:
                self._csi(m.group(1), m.group(2), m.group(3))
                return m.end() - i
            partial = _CSI_PARTIAL.match(text, i)
            if partial and partial.end() == len(text) and len(text) - i < 32:
                return 0
            return 2
        if nxt == "]":
            # OSC (창 제목 등): BEL 또는 ESC \ 까지 무시
            for end_mark, extra in (("\x07", 1), ("\x1b\\", 2)):
                j = text.find(end_mark, i + 2)
                if j >= 0:
                    return j + extra - i
            return 0 if len(text) - i < 256 else 2
        if nxt == "7":
            self._saved = (self.cx, self.cy - self.top)
            return 2
        if nxt == "8":
            self._restore()
            return 2
        if nxt == "c":
            self.reset()
            return 2
        return 2

    def _control(self, ch: str) -> None:
        if ch == "\r":
            self.cx = 0
        elif ch == "\n":
            self._newline()
            if self.lf_implies_cr:
                self.cx = 0
        elif ch == "\b":
            self.cx = max(0, min(self.cx, self.cols) - 1)
        elif ch == "\t":
            self.cx = min(self.cols - 1, (self.cx // 8 + 1) * 8)
        # BEL 등 나머지 제어 문자는 무시

    def _newline(self) -> None:
        self.cy += 1
        while self.cy >= len(self.lines):
            self.lines.append([])
            self.stamps.append(self.clock())

    def _line(self) -> list[tuple[str, tuple]]:
        line = self.lines[self.cy]
        if len(line) < self.cx:
            line.extend([BLANK] * (self.cx - len(line)))
        return line

    def _print(self, s: str) -> None:
        style = self.style
        if s.isascii() and not self.insert_mode:
            # 흔한 경우(ASCII 한 덩어리)는 줄 끝까지 잘라서 한 번에 넣는다
            while s:
                if self.cx >= self.cols:
                    if not self.wrap:
                        self.cx = self.cols - 1
                    else:
                        self._newline()
                        self.cx = 0
                room = self.cols - self.cx
                part, s = s[:room], s[room:]
                line = self._line()
                end = self.cx + len(part)
                if end < len(line) and line[end][0] == WIDE_CONT:
                    line[end] = BLANK
                if self.cx > 0 and self.cx < len(line) and line[self.cx][0] == WIDE_CONT:
                    line[self.cx - 1] = BLANK
                line[self.cx : end] = [(c, style) for c in part]
                self.cx = end
            return

        for ch in s:
            w = char_width(ch)
            if w == 0:
                continue
            if self.cx + w > self.cols:
                if self.wrap:
                    self._newline()
                    self.cx = 0
                else:
                    self.cx = self.cols - w
            line = self._line()
            cells = [(ch, style)] + ([(WIDE_CONT, style)] if w == 2 else [])
            if self.insert_mode:
                line[self.cx : self.cx] = cells
                del line[self.cols :]
            else:
                if self.cx > 0 and self.cx < len(line) and line[self.cx][0] == WIDE_CONT:
                    line[self.cx - 1] = BLANK
                end = self.cx + w
                if end < len(line) and line[end][0] == WIDE_CONT:
                    line[end] = BLANK
                line[self.cx : end] = cells
            self.cx += w

    def _csi(self, private: str, params: str, final: str) -> None:
        ps = [int(p) if p else 0 for p in params.split(";")] if params else []

        def arg(k: int, default: int) -> int:
            v = ps[k] if len(ps) > k else 0
            return v if v else default

        if private == "?":
            if params == "25" and final in "hl":
                self.cursor_visible = final == "h"
            return

        cols = self.cols
        if final == "A":
            self.cy = max(self.top, self.cy - arg(0, 1))
        elif final == "B":
            self.cy = min(len(self.lines) - 1, self.cy + arg(0, 1))
        elif final == "C":
            self.cx = min(cols - 1, self.cx + arg(0, 1))
        elif final == "D":
            self.cx = max(0, min(self.cx, cols) - arg(0, 1))
        elif final == "G":
            self.cx = min(cols - 1, arg(0, 1) - 1)
        elif final in "Hf":
            row = min(self.rows - 1, arg(0, 1) - 1)
            self.cy = self.top + row
            while self.cy >= len(self.lines):
                self.lines.append([])
                self.stamps.append(self.clock())
            self.cx = min(cols - 1, arg(1, 1) - 1)
        elif final == "J":
            mode = ps[0] if ps else 0
            if mode in (2, 3):
                for li in range(self.top, len(self.lines)):
                    self.lines[li] = []
            elif mode == 0:
                del self._line()[self.cx :]
                for li in range(self.cy + 1, len(self.lines)):
                    self.lines[li] = []
        elif final == "K":
            mode = ps[0] if ps else 0
            line = self._line()
            if mode == 0:
                del line[self.cx :]
            elif mode == 1:
                line[: self.cx + 1] = [BLANK] * min(len(line), self.cx + 1)
            elif mode == 2:
                self.lines[self.cy] = []
        elif final == "P":
            line = self._line()
            del line[self.cx : self.cx + arg(0, 1)]
        elif final == "@":
            line = self._line()
            line[self.cx : self.cx] = [BLANK] * arg(0, 1)
            del line[cols:]
        elif final == "X":
            line = self._line()
            n = arg(0, 1)
            end = min(len(line), self.cx + n)
            line[self.cx : end] = [BLANK] * (end - self.cx)
        elif final == "m":
            self._sgr(ps or [0])
        elif final in "hl" and params == "4":
            self.insert_mode = final == "h"
        elif final == "s":
            self._saved = (self.cx, self.cy - self.top)
        elif final == "u":
            self._restore()

    def _restore(self) -> None:
        cx, row = self._saved
        self.cx = min(cx, self.cols - 1)
        self.cy = min(len(self.lines) - 1, self.top + row)

    def _sgr(self, ps: list[int]) -> None:
        fg, bg, flags = self.style
        i = 0
        while i < len(ps):
            p = ps[i]
            i += 1
            if p in (38, 48) and i < len(ps):
                # 확장 색: 38;5;n (256색) / 38;2;r;g;b (트루컬러). 48 은 배경
                mode = ps[i]
                if mode == 5 and i + 1 < len(ps):
                    color = _xterm256(ps[i + 1])
                    i += 2
                elif mode == 2 and i + 3 < len(ps):
                    color = tuple(max(0, min(255, v)) for v in ps[i + 1 : i + 4])
                    i += 4
                else:
                    i += 1
                    continue
                if p == 38:
                    fg = color
                else:
                    bg = color
                continue
            if p == 0:
                fg, bg, flags = None, None, 0
            elif p == 1:
                flags |= BOLD
            elif p == 4:
                flags |= UNDERLINE
            elif p == 7:
                flags |= REVERSE
            elif p == 22:
                flags &= ~BOLD
            elif p == 24:
                flags &= ~UNDERLINE
            elif p == 27:
                flags &= ~REVERSE
            elif 30 <= p <= 37:
                fg = p - 30
            elif p == 39:
                fg = None
            elif 40 <= p <= 47:
                bg = p - 40
            elif p == 49:
                bg = None
            elif 90 <= p <= 97:
                fg = p - 90 + 8
            elif 100 <= p <= 107:
                bg = p - 100 + 8
        self.style = (fg, bg, flags)

    def _trim(self) -> None:
        excess = len(self.lines) - (self.max_lines + self.rows)
        if excess > _TRIM_SLACK:
            del self.lines[:excess]
            del self.stamps[:excess]
            self.cy = max(0, self.cy - excess)
            self.dropped += excess


# ---- widget ----------------------------------------------------------------


@dataclass
class HighlightRule:
    """정규식에 맞는 글자의 색을 바꾼다. 원래 기본색인 글자에만 적용해서 펌웨어가 보낸 ANSI 색은 존중한다."""

    pattern: re.Pattern
    fg: RGB
    bold: bool = False

    @classmethod
    def of(cls, pattern: str, fg: RGB, bold: bool = False, flags: int = 0) -> HighlightRule:
        return cls(re.compile(pattern, flags), fg, bold)


_GUTTER = 13  # "HH:MM:SS.mmm "


class Terminal(Widget):
    focusable = True
    wants_text_input = True

    def __init__(
        self,
        *,
        max_lines: int = 5000,
        show_timestamps: bool = False,
        enter: bytes = b"\r",
        backspace: bytes = b"\x08",
        stretch: int = 1,
        clock: Callable[[], float] = time.time,
        **kw,
    ):
        super().__init__(stretch=stretch, **kw)
        self.screen = TerminalScreen(80, 24, max_lines, clock=clock)
        self.show_timestamps = show_timestamps
        # 펌웨어 CLI 는 Backspace 를 0x08 로만 처리하고 0x7F 는 커서 위치 삭제로 쓴다
        self.enter = enter
        self.backspace = backspace
        self.rules: list[HighlightRule] = []
        self.send = Signal()  # bytes: 키 입력을 장치로 보낼 때
        self.scroll_offset = 0

    # ---- data ----------------------------------------------------------

    def feed(self, text: str) -> None:
        scr = self.screen
        before = len(scr.lines) + scr.dropped
        scr.feed(text)
        if self.scroll_offset:
            # 스크롤해서 과거를 보는 중에는 새 줄이 와도 보던 화면을 유지한다
            self.scroll_offset += len(scr.lines) + scr.dropped - before
            self._clamp_scroll()
        self.invalidate()

    def clear(self) -> None:
        self.screen.clear()
        self.scroll_offset = 0
        self.invalidate()

    def set_show_timestamps(self, show: bool) -> None:
        self.show_timestamps = show
        self.relayout()
        self.invalidate()

    @property
    def gutter(self) -> int:
        return _GUTTER if self.show_timestamps else 0

    def scroll(self, delta: int) -> None:
        self.scroll_offset += delta
        self._clamp_scroll()
        self.invalidate()

    def _clamp_scroll(self) -> None:
        max_offset = max(0, len(self.screen.lines) - max(1, self.rect.h))
        self.scroll_offset = max(0, min(self.scroll_offset, max_offset))

    # ---- layout / paint ------------------------------------------------

    def size_hint(self) -> SizeHint:
        return SizeHint(10, 3, 80, 24)

    def _do_layout(self, rect: Rect) -> None:
        super()._do_layout(rect)
        self.screen.resize(max(1, rect.w - self.gutter), max(1, rect.h))
        self._clamp_scroll()

    def _style_colors(self, style: tuple) -> tuple[RGB, RGB, int]:
        pal = self.palette
        fg_i, bg_i, flags = style
        if isinstance(fg_i, int) and flags & BOLD and fg_i < 8:
            fg_i += 8
        fg = pal.fg if fg_i is None else fg_i if isinstance(fg_i, tuple) else ANSI_COLORS[fg_i]
        bg = pal.bg if bg_i is None else bg_i if isinstance(bg_i, tuple) else ANSI_COLORS[bg_i]
        attr = 0
        if flags & BOLD:
            attr |= Attr.BOLD
        if flags & UNDERLINE:
            attr |= Attr.UNDERLINE
        if flags & REVERSE:
            attr |= Attr.REVERSE
        return fg, bg, attr

    def _highlights(self, line: list[tuple[str, tuple]]) -> dict[int, tuple[RGB, bool]]:
        if not self.rules or not line:
            return {}
        chars = []
        index = []
        for x, (ch, _) in enumerate(line):
            if ch != WIDE_CONT:
                chars.append(ch)
                index.append(x)
        text = "".join(chars)
        out: dict[int, tuple[RGB, bool]] = {}
        for rule in self.rules:
            for m in rule.pattern.finditer(text):
                for k in range(m.start(), m.end()):
                    out.setdefault(index[k], (rule.fg, rule.bold))
        return out

    def view_top(self) -> int:
        return max(0, len(self.screen.lines) - self.rect.h - self.scroll_offset)

    def paint(self, p: Painter) -> None:
        pal = self.palette
        scr = self.screen
        w, h = self.rect.w, self.rect.h
        gutter = self.gutter
        p.fill(Rect(0, 0, w, h), " ", pal.fg, pal.bg)
        top = self.view_top()

        for row in range(h):
            li = top + row
            if li >= len(scr.lines):
                break
            if gutter:
                stamp = scr.stamps[li]
                ms = int((stamp % 1) * 1000)
                p.text(0, row, time.strftime("%H:%M:%S", time.localtime(stamp)) + f".{ms:03d}", pal.dim, pal.bg)
            line = scr.lines[li]
            marks = self._highlights(line)
            for x, (ch, style) in enumerate(line):
                if ch == WIDE_CONT:
                    continue
                if gutter + x >= w:
                    break
                fg, bg, attr = self._style_colors(style)
                mark = marks.get(x)
                if mark is not None and style[0] is None:
                    fg = mark[0]
                    if mark[1]:
                        attr |= Attr.BOLD
                p.put(gutter + x, row, ch, fg, bg, attr)

        if self.focused and scr.cursor_visible and self.scroll_offset == 0:
            row = scr.cy - top
            col = min(scr.cx, scr.cols - 1)
            if 0 <= row < h:
                line = scr.lines[scr.cy]
                ch = line[col][0] if col < len(line) and line[col][0] != WIDE_CONT else " "
                p.put(gutter + col, row, ch, pal.fg, pal.bg, Attr.REVERSE)

        if self.scroll_offset:
            label = f" ↑{self.scroll_offset} "
            p.text(max(0, w - len(label)), 0, label, pal.bg, pal.warn)

    def caret_cell(self) -> tuple[int, int] | None:
        if not self.focused:
            return None
        row = self.screen.cy - self.view_top()
        return self.rect.x + self.gutter + min(self.screen.cx, self.screen.cols - 1), self.rect.y + max(0, min(row, self.rect.h - 1))

    # ---- input ---------------------------------------------------------

    _KEY_SEQ = {
        Key.UP: b"\x1b[A",
        Key.DOWN: b"\x1b[B",
        Key.RIGHT: b"\x1b[C",
        Key.LEFT: b"\x1b[D",
        Key.HOME: b"\x1b[1~",
        Key.END: b"\x1b[4~",
        Key.INSERT: b"\x1b[2~",
        Key.PAGEUP: b"\x1b[5~",
        Key.PAGEDOWN: b"\x1b[6~",
        Key.DELETE: b"\x7f",
        Key.TAB: b"\t",
        Key.ESCAPE: b"\x1b",
    }

    def key_bytes(self, ev: KeyEvent) -> bytes | None:
        k = ev.key
        if ev.is_enter:
            return self.enter
        if k == Key.BACKSPACE:
            return self.backspace
        if ev.mod & Mod.CTRL and not ev.mod & (Mod.META | Mod.ALT) and len(ev.name) == 1 and "a" <= ev.name <= "z":
            return bytes([ord(ev.name) - ord("a") + 1])
        return self._KEY_SEQ.get(k)

    def _send(self, data: bytes) -> None:
        if data:
            if self.scroll_offset:
                self.scroll_offset = 0
                self.invalidate()
            self.send.emit(data)

    def on_event(self, ev: Event) -> bool:
        if isinstance(ev, TextEvent):
            self._send(ev.text.encode("utf-8"))
            return True
        if isinstance(ev, CompositionEvent):
            return True
        if isinstance(ev, KeyEvent):
            k = ev.key
            if ev.shift and k in (Key.PAGEUP, Key.PAGEDOWN):
                page = max(1, self.rect.h - 1)
                self.scroll(page if k == Key.PAGEUP else -page)
                return True
            if ev.primary and k == Key.V:
                text = clipboard_get().replace("\r\n", "\n").replace("\n", "\r")
                self._send(text.encode("utf-8"))
                return True
            if ev.primary and not ev.mod & Mod.CTRL:
                return False  # Cmd 단축키는 앱으로 (macOS)
            seq = self.key_bytes(ev)
            if seq is not None:
                self._send(seq)
                return True
            return False
        if isinstance(ev, WheelEvent):
            self.scroll(int(round(ev.dy * 3)) or (1 if ev.dy > 0 else -1))
            return True
        if isinstance(ev, MouseEvent):
            return ev.kind == "down" and ev.button == 1
        return False
