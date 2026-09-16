"""Pull-down menus: MenuBar, Menu, MenuItem.

키보드: F10 으로 메뉴바 진입/해제, Alt+니모닉으로 해당 메뉴 열기, ←/→ 메뉴 이동,
↑/↓ 항목 이동, Enter/Space 실행, Esc 닫기, 항목의 key/니모닉 글자로 바로 실행.
마우스: 제목 클릭으로 열고 닫기, 누른 채 항목까지 끌어 놓으면 실행,
메뉴가 열린 상태에서 다른 제목 위로 움직이면 그 메뉴로 전환.
"""

from __future__ import annotations

from typing import Callable, Sequence

from retroui.core.geometry import Rect
from retroui.core.signal import Signal
from retroui.core.wcwidth import str_width
from retroui.input.events import IS_MAC, Event, Key, KeyEvent, Mod, MouseEvent
from retroui.render.painter import Painter
from retroui.widgets.base import SizeHint, Widget
from retroui.widgets.button import draw_mnemonic, parse_mnemonic
from retroui.widgets.popup import Popup

CHECK_MARK = "√"
SUBMENU_MARK = "▶"  # ▸ 는 폰트에서 작게 보인다


class MenuItem:
    def __init__(
        self,
        text: str = "",
        action: Callable[[], None] | None = None,
        *,
        shortcut: str = "",
        key: str = "",
        checked: bool | None = None,
        enabled: bool = True,
        separator: bool = False,
        submenu: Sequence["MenuItem"] | None = None,
    ):
        """
        shortcut: 오른쪽에 표시할 단축키 글자 ('F1', 'Primary+Q' -> macOS 'Cmd+Q'). 표시만 한다.
        key     : 오른쪽 끝에 표시하고, 메뉴가 열려 있을 때 누르면 바로 실행되는 글자.
        checked : None 이면 체크 항목이 아니다. bool 이면 실행할 때 먼저 토글된다.
        """
        self.text, self.mnemonic = parse_mnemonic(text)
        self.action = action
        self.shortcut = shortcut
        self.key = key.upper()[:1]
        self.checked = checked
        self.enabled = enabled
        self.separator = separator
        # 2단 메뉴: 이 항목을 고르면 옆에 다시 펼쳐지는 항목들
        self.submenu = list(submenu) if submenu else []

    @classmethod
    def sep(cls) -> MenuItem:
        return cls(separator=True)

    @property
    def selectable(self) -> bool:
        return self.enabled and not self.separator

    @property
    def shortcut_label(self) -> str:
        return self.shortcut.replace("Primary", "Cmd" if IS_MAC else "Ctrl")

    def hotkeys(self) -> set[str]:
        keys = set()
        if self.key:
            keys.add(self.key.lower())
        if self.mnemonic is not None:
            keys.add(self.text[self.mnemonic].lower())
        return keys


class Menu:
    def __init__(self, title: str, items: Sequence[MenuItem]):
        self.title, self.mnemonic = parse_mnemonic(title)
        self.items = list(items)

    @property
    def mnemonic_key(self) -> str | None:
        return None if self.mnemonic is None else self.title[self.mnemonic].lower()


class MenuBar(Widget):
    def __init__(self, menus: Sequence[Menu], **kw):
        super().__init__(**kw)
        self.menus = list(menus)
        self.triggered = Signal()
        self.open_index: int | None = None
        self._popup: MenuPopup | None = None
        self._dragging = False

    @property
    def popup(self) -> MenuPopup | None:
        return self._popup

    def _spans(self) -> list[tuple[int, int]]:
        """메뉴 제목별 (로컬 x, 폭). 제목 양옆에 한 칸씩 여백."""
        spans = []
        x = 1
        for m in self.menus:
            w = str_width(m.title) + 2
            spans.append((x, w))
            x += w
        return spans

    def size_hint(self) -> SizeHint:
        w = sum(w for _, w in self._spans()) + 1
        return SizeHint(1, 1, w, 1, max_h=1)

    def title_at(self, cx: int, cy: int) -> int | None:
        if cy != self.rect.y:
            return None
        lx = cx - self.rect.x
        for i, (x, w) in enumerate(self._spans()):
            if x <= lx < x + w:
                return i
        return None

    def paint(self, p: Painter) -> None:
        pal = self.palette
        p.fill(Rect(0, 0, self.rect.w, 1), " ", pal.fg, pal.bg)
        for i, (m, (x, w)) in enumerate(zip(self.menus, self._spans())):
            if i == self.open_index:
                fg, bg = pal.sel_fg, pal.sel_bg
            else:
                fg, bg = pal.fg, pal.bg
            p.fill(Rect(x, 0, w, 1), " ", fg, bg)
            draw_mnemonic(p, x + 1, 0, m.title, m.mnemonic, fg, bg)

    # ---- open / close --------------------------------------------------

    def open_menu(self, index: int) -> None:
        app = self.app
        if app is None or not self.menus:
            return
        index %= len(self.menus)
        if self._popup is not None:
            old = self._popup
            self._popup = None
            old.close()
        x, _ = self._spans()[index]
        popup = MenuPopup(self, self.menus[index])
        popup.owner = self
        self.open_index = index
        self._popup = popup
        # 상자 왼쪽 테두리가 제목 강조 막대의 바로 왼쪽에 오도록
        app.open_popup(popup, self.rect.x + x - 1, self.rect.y + 1)
        self.invalidate()

    def close_menu(self) -> None:
        if self._popup is not None:
            popup = self._popup
            self._popup = None
            popup.close()
        if self.open_index is not None:
            self.open_index = None
            self.invalidate()

    def open_adjacent(self, delta: int) -> None:
        if self.open_index is not None:
            self.open_menu(self.open_index + delta)

    def _popup_closed(self, popup: MenuPopup) -> None:
        # 바깥 클릭 등 메뉴바를 거치지 않고 닫힌 경우 상태를 맞춘다
        if popup is self._popup:
            self._popup = None
            self.open_index = None
            self.invalidate()

    def activate(self, item: MenuItem) -> None:
        if not item.selectable:
            return
        # 체크 항목은 메뉴를 열어 둔다: 여러 개를 연달아 켜고 끌 때 매번 다시 열지 않아도 된다.
        # 그 밖의 항목은 대화상자를 여는 경우가 많아 먼저 닫는다
        keep_open = item.checked is not None
        if not keep_open:
            self.close_menu()
        if item.checked is not None:
            item.checked = not item.checked
        if item.action is not None:
            item.action()
        if keep_open and self._popup is not None:
            self._popup.invalidate()
            if self._popup.child is not None:
                self._popup.child.invalidate()
        self.triggered.emit(item)

    # ---- input ---------------------------------------------------------

    def global_key(self, ev: KeyEvent) -> bool:
        """포커스 위젯이 처리하지 않은 키. App 이 레이아웃 때 수집해서 호출한다."""
        if ev.key == Key.F10 and not ev.mod:
            if self._popup is not None:
                self.close_menu()
            else:
                self.open_menu(0)
            return True
        if ev.alt and not (ev.mod & (Mod.CTRL | Mod.META)):
            name = ev.name.lower()
            for i, m in enumerate(self.menus):
                if m.mnemonic_key == name:
                    self.open_menu(i)
                    return True
        return False

    def on_event(self, ev: Event) -> bool:
        if not isinstance(ev, MouseEvent):
            return False
        popup = self._popup
        if ev.kind == "down" and ev.button == 1:
            i = self.title_at(ev.cx, ev.cy)
            if i is None:
                return False
            if i == self.open_index:
                self.close_menu()
            else:
                self.open_menu(i)
                self._dragging = True
            return True
        if ev.kind == "move":
            if popup is not None and popup.rect.contains(ev.cx, ev.cy):
                popup.track(ev)
                return True
            i = self.title_at(ev.cx, ev.cy)
            if popup is not None and i is not None and i != self.open_index:
                self.open_menu(i)
            return self._dragging
        if ev.kind == "up" and ev.button == 1:
            dragging = self._dragging
            self._dragging = False
            if dragging and popup is not None and popup.rect.contains(ev.cx, ev.cy):
                popup.release(ev)
            return dragging
        return False


class MenuPopup(Popup):
    focusable = True

    def __init__(self, bar: MenuBar, menu: Menu, parent_popup: "MenuPopup | None" = None):
        super().__init__()
        self.bar = bar
        self.menu = menu
        self.parent_popup = parent_popup
        self.child: MenuPopup | None = None
        self.selected = next((i for i, it in enumerate(menu.items) if it.selectable), -1)

    def open_submenu(self, row: int) -> "MenuPopup | None":
        """row 항목의 2단 메뉴를 옆에 연다. 오른쪽이 좁으면 왼쪽으로."""
        item = self.menu.items[row]
        app = self.app
        if not item.submenu or app is None:
            return None
        if self.child is not None and self.child.menu.items is item.submenu:
            return self.child
        self.close_submenu()
        popup = MenuPopup(self.bar, Menu(item.text, item.submenu), parent_popup=self)
        popup.owner = self
        popup._app = app
        hint = popup.effective_hint()
        x = self.rect.right - 1
        if x + hint.pref_w > app.cols:
            x = max(0, self.rect.x - hint.pref_w + 1)
        # 테두리 한 줄을 감안해 부모 항목과 같은 줄에서 시작하게 한 줄 위로
        y = min(self.rect.y + row, max(0, app.rows - hint.pref_h))
        self.child = popup
        app.open_popup(popup, x, y)
        return popup

    def close_submenu(self) -> None:
        if self.child is not None:
            child, self.child = self.child, None
            child.close()

    def _columns(self) -> tuple[bool, int, int, bool]:
        items = [i for i in self.menu.items if not i.separator]
        has_check = any(i.checked is not None for i in items)
        text_w = max((str_width(i.text) for i in items), default=0)
        shortcut_w = max((str_width(i.shortcut_label) for i in items), default=0)
        has_key = any(i.key for i in items)
        return has_check, text_w, shortcut_w, has_key or any(i.submenu for i in items)

    def size_hint(self) -> SizeHint:
        has_check, text_w, shortcut_w, has_key = self._columns()
        # │ [√ ]글자[  단축키][  K] │
        inner = 1 + (2 if has_check else 0) + text_w + (2 + shortcut_w if shortcut_w else 0) + (3 if has_key else 0) + 1
        w = max(inner + 2, str_width(self.menu.title) + 4)
        h = len(self.menu.items) + 2
        return SizeHint(w, h, w, h)

    def paint(self, p: Painter) -> None:
        theme = self.theme
        pal = theme.palette
        box = theme.box
        w, h = self.rect.w, self.rect.h
        p.box(Rect(0, 0, w, h), box, pal.border, pal.bg)
        has_check, _, _, has_key = self._columns()
        x_text = 2 + (2 if has_check else 0)
        shortcut_end = w - 2 - (3 if has_key else 0)

        for row, item in enumerate(self.menu.items):
            y = row + 1
            if y >= h - 1:
                break
            if item.separator:
                p.put(0, y, box.tee_right, pal.border, pal.bg)
                p.hline(1, y, w - 2, box.h, pal.border, pal.bg)
                p.put(w - 1, y, box.tee_left, pal.border, pal.bg)
                continue
            selected = row == self.selected
            if not item.enabled:
                fg, bg = pal.disabled, pal.bg
            elif selected:
                fg, bg = pal.sel_fg, pal.sel_bg
            else:
                fg, bg = pal.fg, pal.bg
            plain = selected or not item.enabled
            p.fill(Rect(1, y, w - 2, 1), " ", fg, bg)
            if item.checked:
                p.put(2, y, CHECK_MARK, fg, bg)
            draw_mnemonic(p, x_text, y, item.text, item.mnemonic, fg, bg)
            if item.shortcut:
                label = item.shortcut_label
                p.text(shortcut_end - str_width(label), y, label, fg if plain else pal.dim, bg)
            if item.submenu:
                p.put(w - 3, y, SUBMENU_MARK, fg if plain else pal.accent, bg)
            elif item.key:
                p.put(w - 3, y, item.key, fg if plain else pal.accent, bg)

    # ---- selection -----------------------------------------------------

    def _selectable_rows(self) -> list[int]:
        return [i for i, it in enumerate(self.menu.items) if it.selectable]

    def select(self, row: int) -> None:
        if row != self.selected:
            self.selected = row
            self.close_submenu()
            self.invalidate()

    def move(self, delta: int) -> None:
        rows = self._selectable_rows()
        if not rows:
            return
        if self.selected not in rows:
            self.select(rows[0] if delta > 0 else rows[-1])
            return
        self.select(rows[(rows.index(self.selected) + delta) % len(rows)])

    def _row_at(self, cx: int, cy: int) -> int | None:
        if not self.rect.inset(1).contains(cx, cy):
            return None
        row = cy - self.rect.y - 1
        return row if self.menu.items[row].selectable else None

    def track(self, ev: MouseEvent) -> None:
        row = self._row_at(ev.cx, ev.cy)
        if row is not None:
            self.select(row)
            if self.menu.items[row].submenu:
                self.open_submenu(row)

    def release(self, ev: MouseEvent) -> None:
        row = self._row_at(ev.cx, ev.cy)
        if row is None:
            return
        if self.menu.items[row].submenu:
            self.open_submenu(row)  # 2단 항목은 실행 대신 펼치기
            return
        self.bar.activate(self.menu.items[row])

    # ---- input ---------------------------------------------------------

    def on_event(self, ev: Event) -> bool:
        if isinstance(ev, KeyEvent):
            # 앱 단축키(Cmd/Ctrl+Q)와 Alt+니모닉(다른 메뉴 열기)은 위로 넘긴다
            if ev.alt or ev.mod & (Mod.CTRL | Mod.META):
                return False
            k = ev.key
            rows = self._selectable_rows()
            if k == Key.UP:
                self.move(-1)
            elif k == Key.DOWN:
                self.move(1)
            elif k == Key.HOME and rows:
                self.select(rows[0])
            elif k == Key.END and rows:
                self.select(rows[-1])
            elif k == Key.LEFT:
                if self.parent_popup is not None:
                    self.parent_popup.close_submenu()  # 2단에서는 한 단계만 접는다
                else:
                    self.bar.open_adjacent(-1)
            elif k == Key.RIGHT:
                if self.selected >= 0 and self.menu.items[self.selected].submenu:
                    self.open_submenu(self.selected)
                else:
                    self.bar.open_adjacent(1)
            elif ev.is_enter or k == Key.SPACE:
                if self.selected >= 0 and self.menu.items[self.selected].submenu:
                    self.open_submenu(self.selected)
                elif self.selected >= 0:
                    self.bar.activate(self.menu.items[self.selected])
            elif k == Key.ESCAPE and self.parent_popup is not None:
                self.parent_popup.close_submenu()
            elif k in (Key.ESCAPE, Key.F10):
                self.bar.close_menu()
            elif len(ev.name) == 1:
                name = ev.name.lower()
                for row, item in enumerate(self.menu.items):
                    if item.selectable and name in item.hotkeys():
                        if item.submenu:
                            self.select(row)
                            self.open_submenu(row)
                        else:
                            self.bar.activate(item)
                        break
            # 메뉴가 열려 있는 동안 나머지 키(Tab 등)는 아래 위젯으로 새지 않게 먹는다
            return True
        if isinstance(ev, MouseEvent):
            if ev.kind in ("move", "down"):
                self.track(ev)
                return True
            if ev.kind == "up":
                self.release(ev)
                return True
        return False

    def on_close(self) -> None:
        self.close_submenu()
        if self.parent_popup is not None:
            if self.parent_popup.child is self:
                self.parent_popup.child = None
            return  # 2단 팝업이 닫혀도 메뉴 전체가 닫힌 것은 아니다
        self.bar._popup_closed(self)
