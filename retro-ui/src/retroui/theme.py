"""Palettes, box-drawing styles and theme presets."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

RGB = tuple[int, int, int]

# CGA 16색: 레트로 룩의 기준 팔레트
BLACK = (0, 0, 0)
BLUE = (0, 0, 170)
GREEN = (0, 170, 0)
CYAN = (0, 170, 170)
RED = (170, 0, 0)
MAGENTA = (170, 0, 170)
BROWN = (170, 85, 0)
LIGHT_GRAY = (170, 170, 170)
DARK_GRAY = (85, 85, 85)
LIGHT_BLUE = (85, 85, 255)
LIGHT_GREEN = (85, 255, 85)
LIGHT_CYAN = (85, 255, 255)
LIGHT_RED = (255, 85, 85)
LIGHT_MAGENTA = (255, 85, 255)
YELLOW = (255, 255, 85)
WHITE = (255, 255, 255)

COLORS: dict[str, RGB] = {
    "black": BLACK, "blue": BLUE, "green": GREEN, "cyan": CYAN, "red": RED, "magenta": MAGENTA,
    "brown": BROWN, "light_gray": LIGHT_GRAY, "dark_gray": DARK_GRAY, "light_blue": LIGHT_BLUE,
    "light_green": LIGHT_GREEN, "light_cyan": LIGHT_CYAN, "light_red": LIGHT_RED,
    "light_magenta": LIGHT_MAGENTA, "yellow": YELLOW, "white": WHITE,
}


@dataclass(frozen=True)
class BoxStyle:
    tl: str
    tr: str
    bl: str
    br: str
    h: str
    v: str
    tee_down: str   # ┬
    tee_up: str     # ┴
    tee_right: str  # ├
    tee_left: str   # ┤
    cross: str      # ┼


BOX_SINGLE = BoxStyle("┌", "┐", "└", "┘", "─", "│", "┬", "┴", "├", "┤", "┼")
BOX_DOUBLE = BoxStyle("╔", "╗", "╚", "╝", "═", "║", "╦", "╩", "╠", "╣", "╬")
BOX_ROUNDED = BoxStyle("╭", "╮", "╰", "╯", "─", "│", "┬", "┴", "├", "┤", "┼")
BOX_HEAVY = BoxStyle("┏", "┓", "┗", "┛", "━", "┃", "┳", "┻", "┣", "┫", "╋")
BOX_ASCII = BoxStyle("+", "+", "+", "+", "-", "|", "+", "+", "+", "+", "+")

BOX_STYLES: dict[str, BoxStyle] = {
    "single": BOX_SINGLE, "double": BOX_DOUBLE, "rounded": BOX_ROUNDED, "heavy": BOX_HEAVY, "ascii": BOX_ASCII,
}


@dataclass(frozen=True)
class Palette:
    bg: RGB
    fg: RGB
    dim: RGB
    accent: RGB
    border: RGB
    border_focus: RGB
    sel_bg: RGB
    sel_fg: RGB
    hover_bg: RGB
    disabled: RGB
    button_bg: RGB
    button_fg: RGB
    input_bg: RGB
    input_fg: RGB
    ok: RGB
    warn: RGB
    error: RGB
    grid: RGB
    axis: RGB
    plot_bg: RGB
    series: tuple[RGB, ...] = field(default=(LIGHT_GREEN, LIGHT_CYAN, YELLOW, LIGHT_MAGENTA, LIGHT_RED, WHITE, LIGHT_BLUE, BROWN))
    button_focus_fg: RGB = WHITE


@dataclass(frozen=True)
class Theme:
    name: str
    palette: Palette
    box: BoxStyle = BOX_SINGLE
    box_focus: BoxStyle = BOX_DOUBLE
    shadow: bool = False  # 버튼/팝업 아래 ▀▄ 그림자 (Turbo Vision 스타일)
    button_style: str = "fill"  # fill: 배경색을 채운 한 줄 버튼, box: 테두리 박스 3줄 버튼

    def with_box(self, box: str | BoxStyle) -> Theme:
        return replace(self, box=BOX_STYLES[box] if isinstance(box, str) else box)


DOS_BLUE = Theme(
    "dos_blue",
    Palette(
        bg=BLUE, fg=LIGHT_GRAY, dim=LIGHT_BLUE, accent=YELLOW,
        border=WHITE, border_focus=LIGHT_CYAN,
        sel_bg=CYAN, sel_fg=BLACK, hover_bg=(0, 0, 220), disabled=DARK_GRAY,
        button_bg=GREEN, button_fg=BLACK, input_bg=(0, 0, 110), input_fg=WHITE,
        ok=LIGHT_GREEN, warn=YELLOW, error=LIGHT_RED,
        grid=(40, 40, 150), axis=LIGHT_GRAY, plot_bg=(0, 0, 80),
    ),
    shadow=True,
)

AMBER = Theme(
    "amber",
    Palette(
        bg=(20, 12, 0), fg=(255, 176, 0), dim=(150, 100, 0), accent=(255, 210, 90),
        border=(200, 135, 0), border_focus=(255, 210, 90),
        sel_bg=(255, 176, 0), sel_fg=(20, 12, 0), hover_bg=(60, 38, 0), disabled=(100, 66, 0),
        button_bg=(90, 58, 0), button_fg=(255, 200, 60), input_bg=(40, 25, 0), input_fg=(255, 200, 60),
        ok=(255, 210, 90), warn=(255, 140, 0), error=(255, 90, 40),
        grid=(70, 45, 0), axis=(200, 135, 0), plot_bg=(12, 7, 0),
        series=((255, 176, 0), (255, 230, 150), (255, 120, 0), (200, 150, 60)),
    ),
)

GREEN_PHOSPHOR = Theme(
    "green_phosphor",
    Palette(
        bg=(0, 16, 0), fg=(51, 255, 51), dim=(20, 130, 20), accent=(170, 255, 170),
        border=(40, 200, 40), border_focus=(170, 255, 170),
        sel_bg=(51, 255, 51), sel_fg=(0, 16, 0), hover_bg=(0, 50, 0), disabled=(20, 90, 20),
        button_bg=(0, 80, 0), button_fg=(170, 255, 170), input_bg=(0, 34, 0), input_fg=(170, 255, 170),
        ok=(170, 255, 170), warn=(220, 255, 80), error=(255, 120, 80),
        grid=(0, 60, 0), axis=(40, 200, 40), plot_bg=(0, 10, 0),
        series=((51, 255, 51), (190, 255, 190), (0, 170, 90), (220, 255, 80)),
    ),
)

MONO_DARK = Theme(
    "mono_dark",
    Palette(
        bg=(18, 18, 20), fg=(200, 200, 200), dim=(110, 110, 115), accent=WHITE,
        border=(120, 120, 125), border_focus=WHITE,
        sel_bg=(200, 200, 200), sel_fg=(18, 18, 20), hover_bg=(45, 45, 50), disabled=(80, 80, 85),
        button_bg=(60, 60, 66), button_fg=WHITE, input_bg=(30, 30, 34), input_fg=WHITE,
        ok=LIGHT_GREEN, warn=YELLOW, error=LIGHT_RED,
        grid=(45, 45, 50), axis=(150, 150, 155), plot_bg=(10, 10, 12),
    ),
    box_focus=BOX_HEAVY,
)

MONO = Theme(
    "mono",
    Palette(
        bg=BLACK, fg=(200, 200, 200), dim=(120, 120, 120), accent=WHITE,
        border=(150, 150, 150), border_focus=WHITE,
        sel_bg=(220, 220, 220), sel_fg=BLACK, hover_bg=(48, 48, 48), disabled=(80, 80, 80),
        button_bg=BLACK, button_fg=(200, 200, 200), input_bg=(24, 24, 24), input_fg=WHITE,
        # 흑백 위주지만 오류는 놓치면 안 되므로 붉은 계열을 남긴다
        ok=WHITE, warn=(230, 230, 230), error=LIGHT_RED,
        # UI 는 흑백이지만 그래프 시리즈는 기본 컬러 팔레트: 흑백이면 여러 시리즈를 구분할 수 없다
        grid=(40, 40, 40), axis=(150, 150, 150), plot_bg=BLACK,
    ),
    box_focus=BOX_HEAVY,
    button_style="box",
)

THEMES: dict[str, Theme] = {t.name: t for t in (DOS_BLUE, AMBER, GREEN_PHOSPHOR, MONO_DARK, MONO)}


def get_theme(theme: str | Theme) -> Theme:
    if isinstance(theme, Theme):
        return theme
    try:
        return THEMES[theme]
    except KeyError:
        raise ValueError(f"unknown theme {theme!r}, available: {', '.join(THEMES)}") from None


def lighten(color: RGB, amount: float = 0.3) -> RGB:
    return tuple(round(c + (255 - c) * amount) for c in color)  # type: ignore[return-value]


def resolve_color(color: str | RGB, palette: Palette | None = None) -> RGB:
    """'light_green' 같은 CGA 이름, 'series0'/'accent' 같은 팔레트 역할, RGB 튜플을 모두 받는다."""
    if not isinstance(color, str):
        return tuple(color)  # type: ignore[return-value]
    if color in COLORS:
        return COLORS[color]
    if palette is not None:
        if color.startswith("series") and color[6:].isdigit():
            return palette.series[int(color[6:]) % len(palette.series)]
        if hasattr(palette, color):
            return getattr(palette, color)
    if color.startswith("#") and len(color) == 7:
        return (int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16))
    raise ValueError(f"unknown color {color!r}")
