"""Application icon drawn in code: a small retro terminal window with a pixel prompt."""

from __future__ import annotations

import io
import struct

import pygame

# 도트 프롬프트 ">" 와 커서. 한 글자 = 한 도트
_PROMPT = (
    "##.........",
    ".##........",
    "..##.......",
    ".##........",
    "##...####..",
)

_BG = (22, 22, 26)
_BAR = (48, 48, 54)
_BORDER = (110, 110, 118)
_PROMPT_FG = (85, 255, 255)
_CURSOR_FG = (240, 240, 240)
_DOTS = ((255, 95, 86), (255, 189, 46), (39, 201, 63))


def make_icon(size: int = 512) -> pygame.Surface:
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    # macOS 아이콘처럼 가장자리에 여백을 두고 둥근 사각형으로
    margin = round(size * 0.09)
    radius = round(size * 0.17)
    body = pygame.Rect(margin, margin, size - 2 * margin, size - 2 * margin)
    pygame.draw.rect(surf, _BG, body, border_radius=radius)

    bar_h = round(body.h * 0.17)
    bar = pygame.Rect(body.x, body.y, body.w, bar_h)
    pygame.draw.rect(surf, _BAR, bar, border_top_left_radius=radius, border_top_right_radius=radius)
    dot_r = max(1, round(bar_h * 0.16))
    for i, color in enumerate(_DOTS):
        cx = body.x + round(bar_h * 0.55) + i * round(dot_r * 3)
        pygame.draw.circle(surf, color, (cx, bar.centery), dot_r)
    pygame.draw.rect(surf, _BORDER, body, width=max(1, size // 96), border_radius=radius)

    unit = body.w // (len(_PROMPT[0]) + 4)
    art_w = unit * len(_PROMPT[0])
    art_h = unit * len(_PROMPT)
    ox = body.x + (body.w - art_w) // 2
    oy = bar.bottom + (body.bottom - bar.bottom - art_h) // 2
    for y, row in enumerate(_PROMPT):
        for x, ch in enumerate(row):
            if ch == "#":
                color = _CURSOR_FG if x >= 5 else _PROMPT_FG
                surf.fill(color, (ox + x * unit, oy + y * unit, unit, unit))
    return surf


# 릴리스 빌드(tools/baram-term.spec)가 실행 파일 아이콘을 만들 때 쓴다. 실행 중에는 위의
# Surface 를 창에 붙이지만, 꺼져 있는 앱의 Dock/탐색기 아이콘은 파일에 박힌 것을 보여 준다.
# 둘 다 PNG 를 그대로 담을 수 있는 형식이라 iconutil 이나 Pillow 없이 어느 OS 에서든 만든다.

# icns 종류 코드와 픽셀 크기. ic04/ic05(16, 32 1배)는 PNG 가 아니라 ARGB 라 빼고, 그 크기는
# macOS 가 가까운 것을 줄여 쓴다
_ICNS_TYPES = (
    (b"ic11", 32),  # 16@2x
    (b"ic12", 64),  # 32@2x
    (b"ic07", 128),
    (b"ic13", 256),  # 128@2x
    (b"ic08", 256),
    (b"ic14", 512),  # 256@2x
    (b"ic09", 512),
    (b"ic10", 1024),  # 512@2x
)
_ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def icon_png(size: int) -> bytes:
    buf = io.BytesIO()
    pygame.image.save(make_icon(size), buf, "icon.png")
    return buf.getvalue()


def icns_bytes() -> bytes:
    pngs: dict[int, bytes] = {}
    body = b""
    for kind, size in _ICNS_TYPES:
        png = pngs.setdefault(size, icon_png(size))
        body += kind + struct.pack(">I", 8 + len(png)) + png
    return b"icns" + struct.pack(">I", 8 + len(body)) + body


def ico_bytes() -> bytes:
    pngs = [icon_png(size) for size in _ICO_SIZES]
    header = struct.pack("<HHH", 0, 1, len(pngs))
    offset = len(header) + 16 * len(pngs)
    entries = b""
    for size, png in zip(_ICO_SIZES, pngs):
        side = size % 256  # 256 은 0 으로 적는다
        entries += struct.pack("<BBBBHHII", side, side, 0, 0, 1, 32, len(png), offset)
        offset += len(png)
    return header + entries + b"".join(pngs)
