"""User highlight rules: "색[ bold]|정규식" 한 줄 형식 (매크로와 같은 방식이라 설정 파일에서 손으로 고치기 쉽다).

색 이름은 테마 색표를 쓴다: 어떤 테마에서도 어울리는 색이 나온다.
사용자 규칙이 기본 규칙(highlight.py)보다 앞에 온다: 같은 글자에는 먼저 맞는 규칙의 색이 쓰인다.
"""

from __future__ import annotations

import re
from typing import Iterable

from retroui import HighlightRule
from retroui.core.geometry import Rect
from retroui.core.wcwidth import str_width
from retroui.render.cellbuffer import Attr
from retroui.render.painter import Painter
from retroui.theme import LIGHT_BLUE, LIGHT_CYAN, LIGHT_GRAY, LIGHT_GREEN, LIGHT_MAGENTA, LIGHT_RED, WHITE, YELLOW
from retroui.widgets.base import SizeHint, Widget

COLORS = {
    "green": LIGHT_GREEN,
    "red": LIGHT_RED,
    "yellow": YELLOW,
    "cyan": LIGHT_CYAN,
    "magenta": LIGHT_MAGENTA,
    "blue": LIGHT_BLUE,
    "white": WHITE,
    "gray": LIGHT_GRAY,
}
DEFAULT_COLOR = "yellow"
BOLD = "bold"
# 규칙을 만들 때 보여주는 예시 줄 (펌웨어 로그에서 자주 보는 모양)
SAMPLE = "[OK] boot 1234 ms  TIMEOUT retry=3  [E_] canOpen()"


def format_entry(color: str, bold: bool, pattern: str) -> str:
    head = f"{color} {BOLD}" if bold else color
    return f"{head}|{pattern}"


def parse_entry(entry: str) -> tuple[str, bool, str] | None:
    """("red", True, r"\\bTIMEOUT\\b"). 형식이 아니면 None."""
    head, sep, pattern = entry.partition("|")
    if not sep or not pattern:
        return None
    words = head.split()
    if not words or words[0] not in COLORS:
        return None
    return words[0], BOLD in words[1:], pattern


def pattern_error(pattern: str) -> str | None:
    """정규식이 잘못됐으면 이유, 괜찮으면 None."""
    try:
        re.compile(pattern)
    except re.error as e:
        return str(e)
    return None


def compile_rules(entries: Iterable[str]) -> list[HighlightRule]:
    """설정에 적힌 줄들을 규칙으로. 형식이나 정규식이 잘못된 줄은 건너뛴다."""
    rules = []
    for entry in entries:
        parsed = parse_entry(entry)
        if parsed is None:
            continue
        color, bold, pattern = parsed
        if pattern_error(pattern) is None:
            rules.append(HighlightRule.of(pattern, COLORS[color], bold))
    return rules


def entry_label(entry: str) -> str:
    """목록에 보여줄 한 줄: "red      bold  \\bTIMEOUT\\b"."""
    parsed = parse_entry(entry)
    if parsed is None:
        return entry
    color, bold, pattern = parsed
    return f"{color:<8} {BOLD if bold else '    '}  {pattern}"


class RulePreview(Widget):
    """규칙을 적용한 예시 줄. 터미널과 같은 방식으로 색을 입힌다 (먼저 맞는 규칙이 이긴다)."""

    def __init__(self, text: str = SAMPLE, **kw):
        super().__init__(**kw)
        self.text = text
        self.rules: list[HighlightRule] = []

    def set_rules(self, rules: Iterable[HighlightRule]) -> None:
        self.rules = list(rules)
        self.invalidate()

    def size_hint(self) -> SizeHint:
        w = str_width(self.text)
        return SizeHint(8, 1, w, 1, max_h=1)

    def colors_at(self) -> dict[int, tuple[tuple[int, int, int], bool]]:
        out: dict[int, tuple[tuple[int, int, int], bool]] = {}
        for rule in self.rules:
            for m in rule.pattern.finditer(self.text):
                for i in range(m.start(), m.end()):
                    out.setdefault(i, (rule.fg, rule.bold))
        return out

    def paint(self, p: Painter) -> None:
        pal = self.palette
        p.fill(Rect(0, 0, self.rect.w, self.rect.h), " ", pal.fg, pal.bg)
        marks = self.colors_at()
        for i, ch in enumerate(self.text[: self.rect.w]):
            fg, bold = marks.get(i, (pal.fg, False))
            p.put(i, 0, ch, fg, pal.bg, Attr.BOLD if bold else 0)
