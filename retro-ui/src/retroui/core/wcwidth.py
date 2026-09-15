"""Terminal-style column width of text (Hangul/CJK = 2 cells).

모호폭(East Asian Ambiguous) 문자는 1칸으로 본다. 박스 문자와 `° ± µ Ω` 같은 공학 기호가
모두 모호폭이라, 2칸으로 보면 테두리와 단위 표기가 격자에서 어긋난다.
"""

from __future__ import annotations

import unicodedata
from functools import lru_cache
from typing import Iterator


def normalize(text: str) -> str:
    # macOS 파일명/IME 는 NFD(자모 분리)로 올 때가 있어 NFC 로 합쳐야 한글이 한 글자로 보인다
    if text.isascii():
        return text
    return unicodedata.normalize("NFC", text)


@lru_cache(maxsize=8192)
def char_width(ch: str) -> int:
    if not ch:
        return 0
    cp = ord(ch)
    if cp < 0x20 or 0x7F <= cp < 0xA0:
        return 0
    if cp < 0x7F:
        return 1
    # 한글 조합형 중성/종성 자모는 앞 초성 셀에 붙는다
    if 0x1160 <= cp <= 0x11FF or 0xD7B0 <= cp <= 0xD7FF:
        return 0
    if unicodedata.category(ch) in ("Mn", "Me", "Cf"):
        return 0
    if unicodedata.east_asian_width(ch) in ("W", "F"):
        return 2
    return 1


def iter_cells(text: str) -> Iterator[tuple[int, str, int]]:
    """(column, char, width) 를 차례로 돌려준다. 폭 0 문자는 건너뛴다."""
    col = 0
    for ch in normalize(text):
        w = char_width(ch)
        if w == 0:
            continue
        yield col, ch, w
        col += w


def str_width(text: str) -> int:
    if text.isascii() and text.isprintable():
        return len(text)
    return sum(w for _, _, w in iter_cells(text))


def slice_cols(text: str, start: int, width: int) -> str:
    """열 구간 [start, start+width) 에 해당하는 부분 문자열.

    경계에 걸친 와이드 문자는 걸친 칸 수만큼 공백으로 바꿔 격자를 깨지 않는다.
    """
    end = start + width
    out = []
    for col, ch, w in iter_cells(text):
        if col >= end:
            break
        if col + w <= start:
            continue
        if col < start or col + w > end:
            out.append(" " * (min(col + w, end) - max(col, start)))
            continue
        out.append(ch)
    return "".join(out)


def truncate(text: str, width: int, ellipsis: str = "…") -> str:
    if width <= 0:
        return ""
    if str_width(text) <= width:
        return text
    ew = str_width(ellipsis)
    if ew >= width:
        return slice_cols(text, 0, width)
    return slice_cols(text, 0, width - ew).rstrip() + ellipsis
