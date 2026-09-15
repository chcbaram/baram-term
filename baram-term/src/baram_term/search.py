"""Scrollback search box (Ctrl-A /, macOS Cmd+F).

입력하는 대로 찾고, 가장 최근 줄에서 시작해 Enter/↑ 로 위(과거)로 올라간다. 대문자가 섞이면 대소문자를 구분한다.
찾는 동안 새 줄이 들어오면 상태 갱신 주기(100ms)에 개수만 다시 센다: 보던 위치로 화면을 끌고 가지 않는다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from retroui import HBox, Label, LineEdit
from retroui.core.geometry import Rect
from retroui.input.events import Event, Key, KeyEvent
from retroui.render.painter import Painter
from retroui.widgets.base import SizeHint
from retroui.widgets.popup import Popup

from baram_term.i18n import tr

if TYPE_CHECKING:
    from retroui import Terminal

    from baram_term.app import BaramTerm

Match = tuple[int, int, int]
_END = (float("inf"), 0)


class SearchBar(Popup):
    def __init__(self, term: BaramTerm):
        super().__init__()
        self.term = term
        self.edit = LineEdit(term.last_search, placeholder=tr("search.placeholder"), on_change=self._on_change, min_size=(24, 1))
        self.count = Label("", min_size=(7, 1))
        self.add(HBox(self.edit, self.count, Label(tr("search.hint"), fg="dim"), spacing=1))
        self.matches: list[Match] = []
        self.index = -1
        self._version = -1

    @property
    def terminal(self) -> Terminal:
        return self.term.terminal

    # ---- popup ---------------------------------------------------------

    def size_hint(self) -> SizeHint:
        h = self.children[0].effective_hint()
        return SizeHint(h.min_w + 2, 3, h.pref_w + 2, 3)

    def layout_children(self) -> None:
        self.children[0]._do_layout(self.rect.inset(1))

    def paint(self, p: Painter) -> None:
        theme = self.theme
        pal = theme.palette
        p.box(Rect(0, 0, self.rect.w, self.rect.h), theme.box, pal.border_focus, pal.bg, title=tr("search.title"), title_fg=pal.accent)

    def open(self) -> None:
        app = self.term.app
        t = self.terminal
        self._app = app
        app.ensure_layout()  # 첫 그리기 전(창을 막 띄운 직후 등)에는 터미널 rect 가 아직 비어 있다
        w = min(self.effective_hint().pref_w, t.rect.w)
        # 터미널 오른쪽 위: CLI 출력은 대개 왼쪽에 짧게 찍혀서 가리는 글자가 적다
        app.open_popup(self, t.rect.right - w, t.rect.y, w, 3)
        if self.edit.text:
            self.edit.select_all()  # 지난번 찾던 글자: 그대로 Enter 로 이어 찾거나 바로 새로 입력
            self._on_change(self.edit.text)

    def on_close(self) -> None:
        self.term.last_search = self.edit.text
        self.terminal.set_search("")
        if self.term.search is self:
            self.term.search = None

    def on_event(self, ev: Event) -> bool:
        if isinstance(ev, KeyEvent):
            k = ev.key
            if k == Key.ESCAPE:
                self.close()
                return True
            if ev.is_enter and not ev.alt:
                self.step(+1 if ev.shift else -1)
                return True
            if k == Key.UP and not ev.mod:
                self.step(-1)
                return True
            if k == Key.DOWN and not ev.mod:
                self.step(+1)
                return True
        return False

    # ---- search --------------------------------------------------------

    def step(self, delta: int) -> None:
        """-1 은 이전(과거) 일치, +1 은 다음 일치. 끝에 닿으면 반대쪽으로 돈다."""
        self.tick()
        if not self.matches:
            return
        if self.index < 0:
            self._select(len(self.matches) - 1)
        else:
            self._select((self.index + delta) % len(self.matches))

    def tick(self) -> None:
        """터미널 내용이 바뀌었으면 일치를 다시 센다. 가리키던 일치는 그대로 두고 스크롤하지 않는다."""
        t = self.terminal
        if t.screen.version == self._version:
            return
        self.matches = t.search_matches()
        self._version = t.screen.version
        cur = t.search_current
        self.index = self.matches.index(cur) if cur in self.matches else -1
        self._update_count()

    def _on_change(self, text: str) -> None:
        t = self.terminal
        cur = t.search_current
        t.set_search(text)
        self.matches = t.search_matches()
        self._version = t.screen.version
        # 한 글자씩 늘려 가며 입력할 때 같은 자리에 머물도록, 가리키던 위치부터 거슬러 찾는다
        anchor = (cur[0], cur[1]) if cur is not None else _END
        before = [i for i, m in enumerate(self.matches) if (m[0], m[1]) <= anchor]
        self._select(before[-1] if before else len(self.matches) - 1)

    def _select(self, index: int) -> None:
        t = self.terminal
        self.index = index
        match = self.matches[index] if 0 <= index < len(self.matches) else None
        t.set_search_current(match)
        if match is not None:
            self._keep_clear(match)
        self._update_count()

    def _keep_clear(self, match: Match) -> None:
        """찾기 상자 밑에 가려지면 가려지지 않을 만큼 더 스크롤한다."""
        t = self.terminal
        row = match[0] - t.screen.dropped - t.view_top()
        end_x = t.rect.x + t.gutter + match[2]
        if 0 <= row < self.rect.h and end_x > self.rect.x:
            t.scroll(self.rect.h - row)

    def _update_count(self) -> None:
        if not self.edit.text:
            text = ""
        elif not self.matches:
            text = tr("search.none")
        elif self.index < 0:
            text = f"-/{len(self.matches)}"
        else:
            text = f"{self.index + 1}/{len(self.matches)}"
        self.count.set_text(text)
