"""Hover tooltip: 위젯 위에 잠깐 머무르면 뜨는 작은 설명 상자.

위젯에 `tooltip = "설명"` 을 넣어 두면 App 이 알아서 띄우고 지운다 (App.tooltip_delay 초).
직접 만들 일은 거의 없다. 여러 줄이면 `\\n` 으로 나눈다.
"""

from __future__ import annotations

from retroui.core.geometry import Rect
from retroui.core.wcwidth import str_width
from retroui.render.painter import Painter
from retroui.widgets.base import SizeHint
from retroui.widgets.popup import Popup

MAX_WIDTH = 60  # 칸. 넘으면 줄바꿈한다


def wrap(text: str, width: int) -> list[str]:
    """칸 폭 기준 줄바꿈. 단어 사이에서 끊고, 한 낱말이 길면 그대로 둔다."""
    lines: list[str] = []
    for raw in text.split("\n"):
        line = ""
        for word in raw.split(" "):
            candidate = f"{line} {word}" if line else word
            if line and str_width(candidate) > width:
                lines.append(line)
                line = word
            else:
                line = candidate
        lines.append(line)
    return lines


class Tooltip(Popup):
    focusable = False
    # 툴팁은 클릭을 먹지 않는다: 바깥을 누르면 닫히고 그 클릭은 아래 위젯으로 간다
    close_on_outside_click = True

    def __init__(self, text: str, **kw):
        super().__init__(**kw)
        self.lines = wrap(text, MAX_WIDTH)

    def size_hint(self) -> SizeHint:
        w = max((str_width(line) for line in self.lines), default=0) + 4
        h = len(self.lines) + 2
        return SizeHint(w, h, w, h, max_w=w, max_h=h)

    def paint(self, p: Painter) -> None:
        pal = self.palette
        p.box(Rect(0, 0, self.rect.w, self.rect.h), self.theme.box, pal.border, pal.bg)
        for i, line in enumerate(self.lines):
            p.text(2, 1 + i, line, pal.fg, pal.bg)
