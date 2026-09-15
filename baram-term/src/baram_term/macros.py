"""F1~F12 매크로 막대: 자주 쓰는 명령을 등록해 두고 키 또는 클릭으로 보낸다.

저장 형식은 `"F5|이름=명령"` 문자열 목록이다 (`Settings.macros`). 설정 파일을 손으로 고칠 수 있게
한 줄짜리 문자열로 뒀다: `["F1|info", "F3|부팅=boot 0"]`.
- `F<번호>|` 가 없으면 남는 번호를 앞에서부터 붙여 준다 (손으로 적을 때는 `"info"` 만 써도 된다).
- 뒤쪽은 `"이름=명령"`. `=` 가 없으면 명령이 곧 이름이다.

키를 매크로가 들고 있어서, 가운데를 지워도 남은 매크로의 F 번호는 그대로다. 막대에는 등록된 것만
번호 순으로 늘어놓고 빈 칸은 그리지 않는다 (번호가 `F1 F3 F7` 처럼 뛸 수 있다).

**F10 은 쓰지 않는다**: 메뉴바 키라서 눌러도 매크로가 안 나간다. 고를 수 있게 두면 안 먹는 칸이
생기므로 목록에서 아예 뺀다 (설정 파일에 F10 이 적혀 있으면 남는 번호로 옮긴다).
"""

from __future__ import annotations

import re
from typing import Callable

from retroui import Button, HBox, Label
from retroui.core.geometry import Rect
from retroui.core.wcwidth import str_width, truncate
from retroui.input.events import Event, MouseEvent
from retroui.widgets.base import SizeHint

from baram_term.i18n import tr

KEY_MAX = 12
MENU_KEY = 10  # F10 은 메뉴바 키라 매크로로 가로채지 않는다 -> 고를 수 없게 뺀다
USABLE_KEYS = tuple(k for k in range(1, KEY_MAX + 1) if k != MENU_KEY)
SLOTS = len(USABLE_KEYS)  # 매크로 최대 개수 (F10 을 빼서 11개)
NAME_MAX = 14  # 버튼에 보일 이름의 최대 칸 수. 넘으면 줄인다 (명령은 그대로 보낸다)
PADDING = 1  # 버튼 글자 좌우 여백. 12칸까지 늘어서므로 기본 2칸은 너무 넓다
# 이름을 이보다 짧게 줄여야 들어간다면 아예 번호만 보여준다.
# `F1 he…` 처럼 두 글자 + 말줄임은 자리만 먹고 무엇인지 알려주지 못했다
NAME_MIN = 4
ADD_LABEL = "+"  # 맨 끝 버튼: 새 매크로 등록 (자리가 되면 "+ 매크로 추가" 로)


_KEY_PREFIX = re.compile(r"^F([1-9]|1[0-2])\|(.*)$", re.S)


def split_entry(entry: str) -> tuple[int | None, str, str]:
    """`"F5|이름=명령"` -> (5, 이름, 명령). 앞머리가 없으면 키는 None."""
    match = _KEY_PREFIX.match(entry.strip())
    key, rest = (int(match.group(1)), match.group(2)) if match else (None, entry)
    name, command = split_macro(rest)
    return key, name, command


def join_entry(key: int, name: str, command: str) -> str:
    body = join_macro(name, command)
    return f"F{key}|{body}" if body else ""


def split_macro(entry: str) -> tuple[str, str]:
    """`"이름=명령"` -> (이름, 명령). `=` 가 없으면 명령을 이름으로 쓴다."""
    name, sep, command = entry.partition("=")
    if not sep:
        return entry.strip(), entry.strip()
    name, command = name.strip(), command.strip()
    return (name or command), command


def join_macro(name: str, command: str) -> str:
    name, command = name.strip(), command.strip()
    if not command:
        return ""
    # 이름을 비워 두면 명령이 곧 이름이다 (버튼에 `F1 info` 로 나온다)
    return command if name in ("", command) else f"{name}={command}"


def normalize(entries: list[str]) -> list[str]:
    """빈 칸을 걷어내고, 키가 없거나 겹치면 남는 번호를 주고, 키 순으로 정렬한다."""
    parsed = [split_entry(e) for e in entries if e.strip()]
    taken: set[int] = set()
    fixed: list[tuple[int, str, str]] = []
    pending: list[tuple[str, str]] = []
    for key, name, command in parsed:
        if key is not None and key != MENU_KEY and key not in taken:
            taken.add(key)
            fixed.append((key, name, command))
        else:
            pending.append((name, command))  # 키가 없거나 이미 쓰인 번호
    free = [k for k in USABLE_KEYS if k not in taken]
    for (name, command), key in zip(pending, free):
        fixed.append((key, name, command))
    fixed.sort()
    return [join_entry(k, n, c) for k, n, c in fixed[:SLOTS]]


def free_keys(entries: list[str], keep: int | None = None) -> list[int]:
    """아직 쓰지 않은 F 번호 (keep 은 지금 고치는 중인 매크로의 번호라 목록에 남긴다)."""
    used = {split_entry(e)[0] for e in entries}
    return [k for k in USABLE_KEYS if k not in used or k == keep]


class MacroBar(HBox):
    """매크로 버튼 한 줄과 끝의 [+] 버튼.

    폭이 모자라면 이름을 줄여서 모두 보여주고, 번호만 남겨도 모자랄 때만 뒤를 접는다.
    """

    def __init__(
        self,
        macros: list[str],
        *,
        on_run: Callable[[int], None],
        on_edit: Callable[[int], None],
        on_menu: Callable[[int, int, int], None] | None = None,
        **kw,
    ):
        super().__init__(spacing=1, **kw)
        self.on_run = on_run
        self.on_edit = on_edit
        # 오른쪽 클릭: (칸 번호, 셀 x, 셀 y). 없으면 바로 편집 창을 연다
        self.on_menu = on_menu
        self.macros = normalize(macros)
        self.buttons: list[Button] = []
        self.more = Label("", fg="dim")  # 폭이 모자라 못 그린 칸 수 (+3)
        self.rebuild()

    # ---- 구성 ----------------------------------------------------------

    def key_of(self, index: int) -> int | None:
        """그 칸에 붙은 F 번호 ([+] 칸이면 None)."""
        if index >= len(self.macros):
            return None
        return split_entry(self.macros[index])[0]

    def index_of_key(self, key: int) -> int | None:
        for i, entry in enumerate(self.macros):
            if split_entry(entry)[0] == key:
                return i
        return None

    def _label(self, index: int, budget: int) -> str:
        """칸 이름을 budget 칸까지 줄인 버튼 글자. budget 0 이면 번호만 (`F12`)."""
        if index >= len(self.macros):
            # 자리가 넉넉할 때만 설명을 붙인다. 좁아지면 `+` 만 남는다
            add = tr("macro.add")
            return f"{ADD_LABEL} {add}" if budget >= str_width(add) else ADD_LABEL
        key, name, _ = split_entry(self.macros[index])
        name = truncate(name, budget) if budget > 0 else ""
        return f"F{key} {name}" if name else f"F{key}"

    def _row_width(self, budget: int) -> int:
        widths = [str_width(self._label(i, budget)) + PADDING * 2 for i in range(len(self.buttons))]
        return sum(widths) + self.spacing * max(0, len(widths) - 1)

    def rebuild(self) -> None:
        for b in self.buttons:
            self.remove(b)
        if self.more.parent is self:
            self.remove(self.more)
        self.buttons = []
        # 등록된 매크로 + (자리가 남으면) 맨 끝 [+]
        count = len(self.macros) + (1 if len(self.macros) < SLOTS else 0)
        for i in range(count):
            add_slot = i >= len(self.macros)
            b = Button(
                self._label(i, NAME_MAX),
                on_click=lambda i=i: self._clicked(i),
                # 매크로는 눌리는 버튼(채운 블록), [+] 는 글자만 흐리게
                style="fill" if add_slot else "solid",
                color="dim",
                padding=PADDING,
            )
            b.focusable = False  # 마우스용 버튼. 키보드 입력은 터미널에 남는다
            # 이름은 줄여서 보여주므로, 올려놓으면 보낼 명령을 그대로 보여준다
            b.tooltip = tr("macro.tip_add") if add_slot else split_entry(self.macros[i])[2]
            self.buttons.append(self.add(b))
        self.add(self.more)

    def set_macros(self, macros: list[str]) -> None:
        self.macros = normalize(macros)
        self.rebuild()

    def _clicked(self, index: int) -> None:
        if index < len(self.macros):
            self.on_run(index)
        else:
            self.on_edit(index)  # [+]: 새로 등록

    def on_event(self, ev: Event) -> bool:
        """오른쪽 클릭은 그 칸을 고친다 (왼쪽 클릭은 보내기라 고칠 길이 따로 필요하다)."""
        if isinstance(ev, MouseEvent) and ev.kind == "down" and ev.button == 3:
            for i, b in enumerate(self.buttons):
                if b.rect.w and b.rect.contains(ev.cx, ev.cy):
                    if i >= len(self.macros):
                        self.on_edit(i)  # [+] 는 지울 것이 없다
                        return True
                    if self.on_menu is not None:
                        self.on_menu(i, b.rect.x, b.rect.y)
                    else:
                        self.on_edit(i)
                    return True
        return False

    # ---- 배치 ----------------------------------------------------------

    def _fit_count(self, width: int, reserve: int) -> int:
        """앞에서부터 폭 안에 들어가는 버튼 수 (reserve 는 +N 표시에 남겨 둘 칸)."""
        x = 0
        for i, b in enumerate(self.buttons):
            w = b.effective_hint().pref_w
            if x + w + reserve > width:
                return i
            x += w + self.spacing
        return len(self.buttons)

    def _apply_labels(self, budget: int) -> None:
        """버튼 글자를 budget 에 맞춰 바꾼다 (배치 중이므로 relayout 을 다시 부르지 않는다)."""
        for i, b in enumerate(self.buttons):
            text = self._label(i, budget)
            if text != b.text:
                b.text, b.mnemonic = text, None
                b.invalidate()

    def layout_children(self) -> None:
        """칸이 많아지면 이름을 줄여서 **다 보여준다**. 그래도 안 들어갈 때만 뒤를 접는다.

        이름을 줄여도 보낼 명령은 그대로고, 마우스를 올리면 툴팁에 전체 명령이 나온다.
        번호(`F12`)까지 줄일 수는 없으니, 번호만 남겨도 모자라면 거기서 멈추고 `+3` 으로 알린다.
        """
        width = self.rect.w
        budget = NAME_MAX
        while budget >= NAME_MIN and self._row_width(budget) > width:
            budget -= 1
        if budget < NAME_MIN:
            budget = 0  # 이름을 살릴 수 없으면 번호만 (명령은 툴팁으로 본다)
        self._apply_labels(budget)

        count = self._fit_count(width, 0)
        hidden = len(self.buttons) - count
        if hidden:
            self.more.set_text(f"+{hidden}")
            count = self._fit_count(width, str_width(self.more.text) + self.spacing)
            hidden = len(self.buttons) - count
        # 한 칸도 못 넣을 만큼 좁으면 첫 칸에 남은 폭을 준다 (버튼이 알아서 글자를 줄인다)
        count = max(count, 1) if self.buttons else 0
        self.more.set_text(f"+{hidden}" if hidden else "")

        x, right = self.rect.x, self.rect.right
        for i, b in enumerate(self.buttons):
            if i >= count:
                b._do_layout(Rect(self.rect.x, self.rect.y, 0, 0))
                continue
            w = min(b.effective_hint().pref_w, max(0, right - x))
            b._do_layout(Rect(x, self.rect.y, w, 1))
            x += w + self.spacing
        if self.more.parent is self:
            w = min(self.more.effective_hint().pref_w, max(0, right - x))
            self.more._do_layout(Rect(x, self.rect.y, w, 1))

    def size_hint(self) -> SizeHint:
        hint = super().size_hint()
        # 한 칸이라도 보이면 되니까 최소 폭은 작게 둔다 (좁은 창에서 막대가 창을 늘리지 않게)
        return SizeHint(1, 1, hint.pref_w, 1, max_h=1)


def bar_width(macros: list[str]) -> int:
    """등록된 내용으로 필요한 대략의 칸 수 (테스트용)."""
    total = 0
    for i, entry in enumerate(normalize(macros)):
        if not entry:
            continue
        total += str_width(f"F{i + 1} {split_macro(entry)[0]}") + 4 + 1
    return total
