"""Tab completion for firmware CLI commands (experimental).

명령 목록은 펌웨어 help 출력("---------- cmd list ---------" ~ "-----------------------------")을
수신 데이터에서 보고 배운다. 목록을 얻으려고 장치에 명령을 몰래 보내지 않는다.

입력 중인 글자는 보낸 키를 따로 기억하지 않고 화면의 커서 줄(프롬프트 뒤)에서 읽는다.
펌웨어가 줄 편집/이력을 직접 처리하므로, 이력(↑)으로 불러온 명령에도 맞게 동작한다.
목록 팝업은 포커스를 가져가지 않는다: 타이핑은 계속 장치로 가고, 에코가 돌아오면 목록이 갱신된다.
"""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING

from retroui import ListPopup
from retroui.input.events import Key, KeyEvent
from retroui.widgets.terminal import WIDE_CONT

from baram_term.i18n import tr

if TYPE_CHECKING:
    from retroui import Terminal

    from baram_term.app import BaramTerm

_ANSI = re.compile(r"\x1b\[[0-9;?]*[@-~]")
_HEADER = re.compile(r"^-{3,}\s*cmd list\s*-{3,}$", re.IGNORECASE)
_FOOTER = re.compile(r"^-{10,}$")
_COMMAND = re.compile(r"^[A-Za-z_][\w.-]*$")
# 프롬프트: 줄 처음의 공백 없는 단어 + "# " (highlight.py 와 같은 규칙)
PROMPT = re.compile(r"^(\S*# )")
# 줄바꿈 없이 계속 들어오는 데이터에 대비한 미완성 줄 한도
_MAX_PENDING = 4096
_VISIBLE_ROWS = 8


class CommandCatalog:
    def __init__(self) -> None:
        self.commands: list[str] = []
        self._pending = ""
        self._collecting: list[str] | None = None

    def feed(self, text: str) -> None:
        lines = (self._pending + text).split("\n")
        self._pending = lines.pop()
        if len(self._pending) > _MAX_PENDING:
            self._pending = ""
        for line in lines:
            self._line(_ANSI.sub("", line).replace("\r", "").strip())

    def _line(self, s: str) -> None:
        if _HEADER.match(s):
            self._collecting = []
            return
        if self._collecting is None:
            return
        if _FOOTER.match(s):
            if self._collecting:
                self.commands = sorted({c.lower() for c in self._collecting})
            self._collecting = None
        elif s and _COMMAND.match(s):
            self._collecting.append(s)
        elif s:
            self._collecting = None  # 명령 목록 형식이 아니면 버린다

    def matches(self, prefix: str) -> list[str]:
        p = prefix.lower()
        return [c for c in self.commands if c.startswith(p)]


def _prompt_line(terminal: Terminal) -> tuple[str, int] | None:
    """커서 줄이 프롬프트 줄이면 (줄 글자, 프롬프트 끝 열)."""
    scr = terminal.screen
    if not 0 <= scr.cy < len(scr.lines):
        return None
    text = "".join(ch for ch, _ in scr.lines[scr.cy] if ch != WIDE_CONT)
    m = PROMPT.match(text)
    if not m or scr.cx < m.end():
        return None
    return text, m.end()


def at_prompt(terminal: Terminal) -> bool:
    """커서가 프롬프트 줄의 입력 위치에 있는가 (명령어 인자를 치는 중이어도 True)."""
    return _prompt_line(terminal) is not None


def current_input(terminal: Terminal) -> tuple[str, int] | None:
    """커서 줄에서 (프롬프트 뒤 입력 중인 명령어, 명령어 시작 열). 명령어 뒤 인자를 치는 중이면 None."""
    line = _prompt_line(terminal)
    if line is None:
        return None
    text, start = line
    typed = text[start : terminal.screen.cx]
    if " " in typed:
        return None
    return typed, start


class Completer:
    def __init__(self, term: BaramTerm):
        self.term = term
        self.catalog = CommandCatalog()
        self.enabled = True
        self.popup: ListPopup | None = None

    @property
    def is_open(self) -> bool:
        return self.popup is not None and self.popup.is_open

    def close(self) -> None:
        if self.popup is not None:
            popup = self.popup
            self.popup = None
            popup.close()

    def on_text(self, text: str) -> None:
        """장치에서 받은 글자. 명령 목록을 배우고, 열린 목록은 에코에 맞춰 갱신한다."""
        self.catalog.feed(text)
        if self.is_open:
            self.refresh()

    def handle_key(self, ev: KeyEvent) -> bool:
        if not self.enabled:
            return False
        if self.is_open:
            popup = self.popup
            assert popup is not None
            k = ev.key
            if k == Key.UP and not ev.mod:
                popup.select(popup.selected - 1)
                return True
            if k == Key.DOWN and not ev.mod:
                popup.select(popup.selected + 1)
                return True
            if (k == Key.TAB or ev.is_enter) and not ev.mod:
                self.accept()
                return True
            if k == Key.ESCAPE:
                self.close()
                return True
            return False  # 나머지 키는 장치로: 에코가 오면 목록이 갱신된다
        if ev.key == Key.TAB and not ev.mod:
            return self.start()
        return False

    def start(self) -> bool:
        cur = current_input(self.term.terminal)
        if cur is None:
            return False  # 프롬프트 줄이 아니면 Tab 을 그대로 장치로
        if not self.catalog.commands:
            self.term.notice(tr("notice.no_commands"))
            return True
        typed, start = cur
        matches = self.catalog.matches(typed)
        if not matches:
            return True
        if len(matches) == 1:
            self._insert(matches[0], typed, space=True)
            return True
        common = os.path.commonprefix(matches)
        if len(common) > len(typed):
            self._insert(common, typed, space=False)
        self._open(matches, start)
        return True

    def refresh(self) -> None:
        popup = self.popup
        if popup is None:
            return
        cur = current_input(self.term.terminal)
        matches = self.catalog.matches(cur[0]) if cur else []
        if not matches:
            self.close()
            return
        if matches == popup.items:
            return
        keep = popup.items[popup.selected] if 0 <= popup.selected < len(popup.items) else None
        popup.set_items(matches, keep)
        hint = popup.effective_hint()
        self.term.app.reposition_popup(popup, popup.rect.x, popup.rect.y, hint.pref_w, hint.pref_h)

    def accept(self) -> None:
        popup = self.popup
        item = popup.items[popup.selected] if popup and 0 <= popup.selected < len(popup.items) else None
        cur = current_input(self.term.terminal)
        self.close()
        if item and cur:
            self._insert(item, cur[0], space=True)

    def _chosen(self, index: int) -> None:
        items = self.popup.items if self.popup else []
        self.popup = None
        cur = current_input(self.term.terminal)
        if cur and 0 <= index < len(items):
            self._insert(items[index], cur[0], space=True)

    def _insert(self, command: str, typed: str, space: bool) -> None:
        # 대문자로 치고 있었으면 대문자로 (펌웨어는 대소문자를 구분하지 않는다)
        text = command.upper() if typed and typed.isupper() else command
        suffix = text[len(typed) :] + (" " if space else "")
        if suffix:
            self.term.send(suffix.encode())

    def _open(self, matches: list[str], start: int) -> None:
        terminal = self.term.terminal
        app = self.term.app
        popup = ListPopup(matches, 0, on_choose=self._chosen, visible_rows=_VISIBLE_ROWS)
        popup._app = app
        hint = popup.effective_hint()
        row = terminal.screen.cy - terminal.view_top()
        # 목록 상자가 입력 중인 명령어 첫 글자 열에서 시작하도록
        x = terminal.rect.x + terminal.gutter + start
        y = terminal.rect.y + row + 1
        if y + hint.pref_h > app.rows:
            y = terminal.rect.y + row - hint.pref_h
        self.popup = popup
        app.open_popup(popup, x, y, focus=False)
