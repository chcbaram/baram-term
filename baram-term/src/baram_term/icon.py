"""Application icon drawn in code: a small retro terminal window with a pixel prompt."""

from __future__ import annotations

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
