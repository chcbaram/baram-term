"""Draw box-drawing and block characters as shapes instead of font glyphs.

폰트 글리프로 그리면 셀 경계에서 1px 틈이 생기거나 폰트마다 선 위치가 달라 테두리가 끊긴다.
셀 중앙 좌표에 사각형으로 직접 그려서 어떤 폰트든 이음매 없이 연결되게 한다.
"""

from __future__ import annotations

import pygame

RGB = tuple[int, int, int]

# (left, right, up, down) 방향별 선 굵기: 0 없음, 1 가는 선, 2 굵은 선
_LINES: dict[str, tuple[int, int, int, int]] = {}


def _add(chars: str, dirs: list[tuple[int, int, int, int]], weight: int) -> None:
    for ch, d in zip(chars, dirs):
        _LINES[ch] = tuple(v * weight for v in d)  # type: ignore[assignment]


_SHAPES = [
    (1, 1, 0, 0),  # ─
    (0, 0, 1, 1),  # │
    (0, 1, 0, 1),  # ┌
    (1, 0, 0, 1),  # ┐
    (0, 1, 1, 0),  # └
    (1, 0, 1, 0),  # ┘
    (0, 1, 1, 1),  # ├
    (1, 0, 1, 1),  # ┤
    (1, 1, 0, 1),  # ┬
    (1, 1, 1, 0),  # ┴
    (1, 1, 1, 1),  # ┼
]
_add("─│┌┐└┘├┤┬┴┼", _SHAPES, 1)
_add("━┃┏┓┗┛┣┫┳┻╋", _SHAPES, 2)
# 둥근 모서리는 레트로 룩에서 각진 모서리로 그린다
_add("╭╮╰╯", _SHAPES[2:6], 1)

_DOUBLE: dict[str, tuple[int, int, int, int]] = dict(zip("═║╔╗╚╝╠╣╦╩╬", _SHAPES))

# 블록 문자: (x0, y0, x1, y1) 을 셀의 1/8 단위로
_BLOCKS: dict[str, tuple[int, int, int, int]] = {
    "█": (0, 0, 8, 8),
    "▀": (0, 0, 8, 4),
    "▔": (0, 0, 8, 1),
    "▐": (4, 0, 8, 8),
    "▕": (7, 0, 8, 8),
    # 사분면: 채워진 박스 버튼의 모서리를 테두리 선 위치(셀 중앙)에 맞출 때 쓴다
    "▖": (0, 4, 4, 8),
    "▗": (4, 4, 8, 8),
    "▘": (0, 0, 4, 4),
    "▝": (4, 0, 8, 4),
}
for _i, _ch in enumerate("▁▂▃▄▅▆▇"):
    _BLOCKS[_ch] = (0, 7 - _i, 8, 8)
for _i, _ch in enumerate("▉▊▋▌▍▎▏"):
    _BLOCKS[_ch] = (0, 0, 7 - _i, 8)

_SHADES = {"░": 0.25, "▒": 0.5, "▓": 0.75}

# 박스 버튼 테두리 문자 (유니코드 사용자 정의 영역, 폰트로는 그리지 않는다). 순서: tl, top, tr, left, right, bl, bottom, br
# 셀 하나에 바깥(bg), 선(fg), 안쪽 채움(attr 의 FILL 색) 세 색을 그린다. 일반 박스 문자처럼 셀 배경을
# 통째로 칠하면 채움이 선 밖으로 번지고, 셀 가장자리에 선을 두면 3줄 버튼이 글자에 비해 너무 크다.
_EDGE_FLAGS = [
    (1, 0, 1, 0),  # tl: top, bottom, left, right
    (1, 0, 0, 0),
    (1, 0, 0, 1),
    (0, 0, 1, 0),
    (0, 0, 0, 1),
    (0, 1, 1, 0),
    (0, 1, 0, 0),
    (0, 1, 0, 1),
]
# 윗변은 윗줄 셀의 이 비율 지점, 아랫변은 아랫줄 셀의 (1 - 비율) 지점에 긋는다.
# 0.7 이면 버튼이 보이는 높이가 약 1.6줄 (Retina 14pt 기준 ~59px, 셀 3줄 전체면 ~111px 로 글자에 비해 컸다)
EDGE_INSET = 0.7
EDGE_LIGHT = tuple(chr(0xE000 + i) for i in range(8))
EDGE_HEAVY = tuple(chr(0xE010 + i) for i in range(8))
_EDGES: dict[str, tuple[int, int, int, int, int]] = {}
for _weight, _chars in ((1, EDGE_LIGHT), (2, EDGE_HEAVY)):
    for _ch, _flags in zip(_chars, _EDGE_FLAGS):
        _EDGES[_ch] = (*_flags, _weight)


def handles(ch: str) -> bool:
    return ch in _LINES or ch in _DOUBLE or ch in _BLOCKS or ch in _SHADES or ch in _EDGES


def _mix(a: RGB, b: RGB, t: float) -> RGB:
    return (round(a[0] * t + b[0] * (1 - t)), round(a[1] * t + b[1] * (1 - t)), round(a[2] * t + b[2] * (1 - t)))


def _single(surf: pygame.Surface, r: pygame.Rect, dirs: tuple[int, int, int, int], fg: RGB, t: int) -> None:
    left, right, up, down = dirs
    cx = r.x + r.w // 2
    cy = r.y + r.h // 2
    for weight, horizontal, toward_start in ((left, True, True), (right, True, False), (up, False, True), (down, False, False)):
        if not weight:
            continue
        s = t * weight
        if horizontal:
            y = cy - s // 2
            if toward_start:
                surf.fill(fg, (r.x, y, cx - s // 2 + s - r.x, s))
            else:
                surf.fill(fg, (cx - s // 2, y, r.right - (cx - s // 2), s))
        else:
            x = cx - s // 2
            if toward_start:
                surf.fill(fg, (x, r.y, s, cy - s // 2 + s - r.y))
            else:
                surf.fill(fg, (x, cy - s // 2, s, r.bottom - (cy - s // 2)))


def _double(surf: pygame.Surface, r: pygame.Rect, ch: str, fg: RGB, t: int) -> None:
    cx = r.x + r.w // 2
    cy = r.y + r.h // 2
    d = max(t, r.w // 6)

    def hline(y: int, xa: int, xb: int) -> None:
        surf.fill(fg, (min(xa, xb), y - t // 2, abs(xb - xa) + t, t))

    def vline(x: int, ya: int, yb: int) -> None:
        surf.fill(fg, (x - t // 2, min(ya, yb), t, abs(yb - ya) + t))

    x0, x1, y0, y1 = r.x, r.right - t, r.y, r.bottom - t
    # 모서리 4종은 바깥선/안쪽선이 교차하지 않도록 따로 그린다
    if ch == "╔":
        hline(cy - d, cx - d, x1); vline(cx - d, cy - d, y1)
        hline(cy + d, cx + d, x1); vline(cx + d, cy + d, y1)
    elif ch == "╗":
        hline(cy - d, x0, cx + d); vline(cx + d, cy - d, y1)
        hline(cy + d, x0, cx - d); vline(cx - d, cy + d, y1)
    elif ch == "╚":
        hline(cy + d, cx - d, x1); vline(cx - d, y0, cy + d)
        hline(cy - d, cx + d, x1); vline(cx + d, y0, cy - d)
    elif ch == "╝":
        hline(cy + d, x0, cx + d); vline(cx + d, y0, cy + d)
        hline(cy - d, x0, cx - d); vline(cx - d, y0, cy - d)
    else:
        left, right, up, down = _DOUBLE[ch]
        if left or right:
            xa = x0 if left else cx - d
            xb = x1 if right else cx + d
            hline(cy - d, xa, xb)
            hline(cy + d, xa, xb)
        if up or down:
            ya = y0 if up else cy - d
            yb = y1 if down else cy + d
            vline(cx - d, ya, yb)
            vline(cx + d, ya, yb)


def draw(
    surf: pygame.Surface, rect: pygame.Rect, ch: str, fg: RGB, bg: RGB, scale: float = 1.0, fill: RGB | None = None
) -> bool:
    """rect(1칸 픽셀 영역) 에 ch 를 도형으로 그린다. 지원하지 않는 문자면 False."""
    t = max(1, round(scale))
    dirs = _LINES.get(ch)
    if dirs is not None:
        _single(surf, rect, dirs, fg, t)
        return True
    if ch in _DOUBLE:
        _double(surf, rect, ch, fg, t)
        return True
    block = _BLOCKS.get(ch)
    if block is not None:
        bx0, by0, bx1, by1 = block
        x0 = rect.x + rect.w * bx0 // 8
        y0 = rect.y + rect.h * by0 // 8
        x1 = rect.x + rect.w * bx1 // 8
        y1 = rect.y + rect.h * by1 // 8
        surf.fill(fg, (x0, y0, max(1, x1 - x0), max(1, y1 - y0)))
        return True
    shade = _SHADES.get(ch)
    if shade is not None:
        surf.fill(_mix(fg, bg, shade), rect)
        return True
    edge = _EDGES.get(ch)
    if edge is not None:
        top, bottom, left, right, weight = edge
        s = t * weight
        # 좌우 변은 셀 중앙, 위아래 변은 EDGE_INSET 지점. 선 안쪽 사각형만 채움색으로 칠한다
        vx = rect.x + rect.w // 2 - s // 2
        x0 = vx if left else rect.x
        x1 = vx + s if right else rect.right
        y0 = rect.y + round(rect.h * EDGE_INSET) if top else rect.y
        y1 = rect.y + round(rect.h * (1 - EDGE_INSET)) if bottom else rect.bottom
        if fill is not None:
            surf.fill(fill, (x0, y0, x1 - x0, y1 - y0))
        if top:
            surf.fill(fg, (x0, y0, x1 - x0, s))
        if bottom:
            surf.fill(fg, (x0, y1 - s, x1 - x0, s))
        if left:
            surf.fill(fg, (x0, y0, s, y1 - y0))
        if right:
            surf.fill(fg, (x1 - s, y0, s, y1 - y0))
        return True
    return False
