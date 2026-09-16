"""Font loading, cell metrics and glyph cache (pygame.freetype).

셀 폭은 주 폰트의 영문 advance, 셀 높이는 줄 높이로 정한다. 모든 글리프는 1칸/2칸 셀
크기 서피스에 미리 그려 캐시하므로, 폭이 다른 fallback 폰트가 섞여도 격자가 깨지지 않는다.
"""

from __future__ import annotations

import glob
import os
from collections import OrderedDict
from dataclasses import dataclass

import pygame
import pygame.freetype

RGB = tuple[int, int, int]

_ASSET_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fonts")
_SEARCH_DIRS = (
    _ASSET_DIR,
    os.path.expanduser("~/Library/Fonts"),
    "/Library/Fonts",
    "/System/Library/Fonts",
    os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts"),
    os.path.expanduser("~/AppData/Local/Microsoft/Windows/Fonts"),
    os.path.expanduser("~/.local/share/fonts"),
    "/usr/share/fonts/truetype",
)

_GLYPH_CACHE_MAX = 8192


@dataclass(frozen=True)
class FontSpec:
    patterns: tuple[str, ...]
    index: int = 0
    antialias: bool = True
    # 픽셀 폰트는 설계 크기의 정수배에서만 선명하므로 px 크기를 이 값의 배수로 맞춘다
    pixel_step: int = 0


FONT_SPECS: dict[str, FontSpec] = {
    "d2coding": FontSpec(("D2Coding.ttf", "D2Coding-Ver*.ttc", "D2Coding*.ttf")),
    "dunggeunmo": FontSpec(("DungGeunMo.ttf",), antialias=False, pixel_step=16),
    "galmuri": FontSpec(("GalmuriMono11.ttf", "Galmuri11.ttf"), antialias=False, pixel_step=12),
}

FALLBACK_PATTERNS = ("AppleSDGothicNeo.ttc", "malgun.ttf", "Menlo.ttc", "consola.ttf", "DejaVuSansMono.ttf")


_FIND_CACHE: dict[tuple[str, ...], "str | None"] = {}


def _find(patterns: tuple[str, ...]) -> str | None:
    """패턴에 맞는 첫 폰트 파일. 못 찾으면 None.

    결과를 기억한다. 프로세스가 도는 동안 폰트 파일은 옮겨 다니지 않는데, 캐시가 없으면
    App 을 하나 만들 때마다 폰트 폴더를 22 번 glob 했다 (본체 1 + 폴백 5 패턴 x 폴더들).
    윈도우는 C:/Windows/Fonts 에 파일이 수천 개인 데다 폴백 목록 첫 항목인
    AppleSDGothicNeo.ttc 가 아예 없어서, 매번 모든 폴더를 끝까지 훑고 실패했다.
    """
    if patterns in _FIND_CACHE:  # None 도 유효한 결과라 get 이 아니라 in 으로 본다
        return _FIND_CACHE[patterns]
    found = None
    for d in _SEARCH_DIRS:
        if not os.path.isdir(d):
            continue
        for pat in patterns:
            hits = sorted(glob.glob(os.path.join(d, pat)))
            if hits:
                found = hits[0]
                break
        if found is not None:
            break
    _FIND_CACHE[patterns] = found
    return found


def resolve_font(font: str) -> tuple[str, FontSpec]:
    if os.path.isfile(font):
        return font, FontSpec((os.path.basename(font),))
    spec = FONT_SPECS.get(font.lower())
    if spec is None:
        raise ValueError(f"unknown font {font!r}: use a file path or one of {', '.join(FONT_SPECS)}")
    path = _find(spec.patterns)
    if path is None:
        raise FileNotFoundError(f"font {font!r} not found (looked for {spec.patterns} in {_SEARCH_DIRS})")
    return path, spec


def _open(path: str, index: int, px: int, antialias: bool) -> pygame.freetype.Font:
    f = pygame.freetype.Font(path, px, font_index=index)
    f.origin = True
    f.pad = False
    f.kerning = False
    f.antialiased = antialias
    return f


def _advance(font: pygame.freetype.Font, ch: str) -> float | None:
    m = font.get_metrics(ch)
    if not m or m[0] is None:
        return None
    return m[0][4]


class FontSet:
    def __init__(self, font: str = "d2coding", size: int = 14, scale: float = 1.0):
        self.font = font
        self.size = size
        self._cache: OrderedDict[tuple, pygame.Surface] = OrderedDict()
        self.reload(scale)

    def reload(self, scale: float) -> None:
        """HiDPI 배율이 바뀌면 px 크기로 다시 열고 캐시를 비운다."""
        if not pygame.freetype.get_init():
            pygame.freetype.init()
        self.scale = scale
        path, spec = resolve_font(self.font)
        px = max(6, round(self.size * scale))
        if spec.pixel_step:
            px = max(spec.pixel_step, round(px / spec.pixel_step) * spec.pixel_step)
        self.path = path
        self.px = px
        self.antialias = spec.antialias
        self._primary = _open(path, spec.index, px, spec.antialias)
        self._fallback_paths = [p for p in (_find((pat,)) for pat in FALLBACK_PATTERNS) if p and p != path]
        self._fallbacks: dict[str, pygame.freetype.Font] = {}
        self._font_for_char: dict[str, pygame.freetype.Font | None] = {}

        self.cw = max(1, round(max(_advance(self._primary, c) or 0 for c in "0MW_")))
        self.ch = max(1, self._primary.get_sized_height())
        self.baseline = self._primary.get_sized_ascender()
        self._cache.clear()

    def _font_for(self, ch: str) -> pygame.freetype.Font | None:
        try:
            return self._font_for_char[ch]
        except KeyError:
            pass
        found = self._primary if _advance(self._primary, ch) is not None else None
        if found is None:
            for path in self._fallback_paths:
                f = self._fallbacks.get(path)
                if f is None:
                    f = self._fallbacks[path] = _open(path, 0, self.px, True)
                if _advance(f, ch) is not None:
                    found = f
                    break
        self._font_for_char[ch] = found
        return found

    def glyph(self, ch: str, fg: RGB, bold: bool = False, width: int = 1) -> pygame.Surface:
        """셀 크기(width 칸 x 1줄)의 투명 서피스에 그린 글리프."""
        key = (ch, fg, bold, width)
        surf = self._cache.get(key)
        if surf is not None:
            self._cache.move_to_end(key)
            return surf

        box_w = self.cw * width
        surf = pygame.Surface((box_w, self.ch), pygame.SRCALPHA)
        font = self._font_for(ch)
        if font is None:
            # 어느 폰트에도 없는 글자: 두부(tofu) 상자
            inset = max(1, self.cw // 6)
            pygame.draw.rect(surf, fg, (inset, inset, box_w - inset * 2, self.ch - inset * 2), max(1, round(self.scale)))
        else:
            style = pygame.freetype.STYLE_STRONG if bold else pygame.freetype.STYLE_DEFAULT
            img, rect = font.render(ch, fgcolor=fg, style=style)
            adv = round(_advance(font, ch) or box_w)
            x = 0 if adv == box_w else (box_w - adv) // 2
            surf.blit(img, (x + rect.x, self.baseline - rect.y))

        self._cache[key] = surf
        if len(self._cache) > _GLYPH_CACHE_MAX:
            self._cache.popitem(last=False)
        return surf
