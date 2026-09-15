"""Start-up banner shown in the terminal (not sent to the device).

로고 글자는 6x6 도트 비트맵으로 정의하고, 반쪽 블록 문자(▀ ▄ █)로 셀 1칸 = 가로 1도트 x 세로 2도트로 그린다.
- D2Coding 셀은 가로:세로가 약 8:19 라 반쪽 블록 도트가 거의 정사각형이고, 글자 비율(약 0.84)이 원본 로고와 비슷하다.
- 글자 높이는 짝수여야 한다: 5도트였을 때는 마지막 줄이 반만 차고 R 다리가 줄 경계에서 뭉개졌다.
- 도트 1개를 "██" 로 그리는 방식은 선명하지만 로고가 5줄 x 58칸으로 너무 컸다.
- 오른쪽 아래 1도트 그림자를 깔아 흰 글자가 검은 배경에서 덜 튀게 한다. 셀 하나에는 도트가 2개뿐이라
  (로고, 그림자, 배경) 중 최대 두 색만 필요하고, 반쪽 블록의 글자색/배경색으로 표현된다.
- 글자 간격 1도트 + ANSI 어두운 회색(85)이면 그림자가 글자 사이와 구멍을 메워 한 덩어리로 보였다.
  간격을 2도트로 늘리고 그림자는 트루컬러로 더 어둡게 한다.
블록 문자는 retro-ui 가 폰트 대신 도형으로 그려서 칸 사이 틈 없이 이어진다.
"""

from __future__ import annotations

from baram_term.i18n import tr

# 모서리를 깎은 굵은 도트 글꼴 (chcbaram 로고의 BARAM 글자 모양을 따름)
GLYPHS: dict[str, tuple[str, ...]] = {
    "B": (
        "#####.",
        "#....#",
        "#####.",
        "#....#",
        "#....#",
        "#####.",
    ),
    "A": (
        ".####.",
        "#....#",
        "#....#",
        "######",
        "#....#",
        "#....#",
    ),
    "R": (
        "#####.",
        "#....#",
        "#....#",
        "#####.",
        "#...#.",
        "#....#",
    ),
    "M": (
        "##..##",
        "#.##.#",
        "#....#",
        "#....#",
        "#....#",
        "#....#",
    ),
}

LOGO_GAP = 2  # 글자 사이 도트
SHADOW_OFFSET = (1, 1)  # (오른쪽, 아래) 도트
SHADOW_RGB = (60, 60, 60)

_EMPTY, _SHADOW, _INK = 0, 1, 2
# SGR 색 코드: 로고는 ANSI 밝은 흰색, 그림자는 트루컬러
_FG = {_EMPTY: None, _SHADOW: "38;2;{};{};{}".format(*SHADOW_RGB), _INK: "97"}
_BG = {_EMPTY: None, _SHADOW: "48;2;{};{};{}".format(*SHADOW_RGB), _INK: "107"}
_HALF = {(True, True): "█", (True, False): "▀", (False, True): "▄", (False, False): " "}

Cell = tuple[str, "str | None", "str | None"]  # (문자, 글자색 SGR, 배경색 SGR)


def word_bitmap(word: str, gap: int = 1) -> list[str]:
    height = max(len(GLYPHS[c]) for c in word)
    rows = []
    for y in range(height):
        parts = [GLYPHS[c][y] if y < len(GLYPHS[c]) else "." * len(GLYPHS[c][0]) for c in word]
        rows.append(("." * gap).join(parts))
    return rows


def bitmap_to_cells(rows: list[str]) -> list[str]:
    """'#' 도트 1개 = "██" (가로 2칸 x 세로 1줄). 크게 그릴 때용."""
    return ["".join("██" if ch == "#" else "  " for ch in row).rstrip() for row in rows]


def bitmap_to_half_cells(rows: list[str]) -> list[str]:
    """'#' 도트 비트맵을 한 가지 색 반쪽 블록 문자로 (가로 1칸 x 세로 2도트)."""
    width = max((len(r) for r in rows), default=0)
    grid = [r.ljust(width, ".") for r in rows]
    if len(grid) % 2:
        grid.append("." * width)
    out = []
    for y in range(0, len(grid), 2):
        top, bottom = grid[y], grid[y + 1]
        out.append("".join(_HALF[(top[x] == "#", bottom[x] == "#")] for x in range(width)).rstrip())
    return out


def compose_shadow(rows: list[str], dx: int, dy: int) -> list[list[int]]:
    """도트 격자: 0 배경, 1 그림자, 2 로고. 로고가 그림자를 덮는다."""
    width = max(len(r) for r in rows)
    grid = [[_EMPTY] * (width + dx) for _ in range(len(rows) + dy)]
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == "#":
                grid[y + dy][x + dx] = _SHADOW
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == "#":
                grid[y][x] = _INK
    return grid


def shaded_cells(grid: list[list[int]]) -> list[list[Cell]]:
    if len(grid) % 2:
        grid = grid + [[_EMPTY] * len(grid[0])]
    lines = []
    for y in range(0, len(grid), 2):
        line: list[Cell] = []
        for top, bottom in zip(grid[y], grid[y + 1]):
            if top == bottom:
                line.append(("█" if top else " ", _FG[top], None))
            elif bottom == _EMPTY:
                line.append(("▀", _FG[top], None))
            elif top == _EMPTY:
                line.append(("▄", _FG[bottom], None))
            else:
                line.append(("▀", _FG[top], _BG[bottom]))
        while line and line[-1][0] == " ":
            line.pop()
        lines.append(line)
    return lines


def cells_to_ansi(line: list[Cell]) -> str:
    parts = []
    current = None
    for ch, fg, bg in line:
        style = (fg, bg) if ch != " " else (None, None)
        if style != current:
            codes = ["0"] + [c for c in style if c is not None]
            parts.append(f"\x1b[{';'.join(codes)}m")
            current = style
        parts.append(ch)
    parts.append(_RESET)
    return "".join(parts)


_RESET = "\x1b[0m"
_SUB_STYLE = "\x1b[0;37m"  # 밝은 회색
_INFO_STYLE = "\x1b[0;90m"  # 어두운 회색

LOGO_CELLS = shaded_cells(compose_shadow(word_bitmap("BARAM", LOGO_GAP), *SHADOW_OFFSET))
LOGO = tuple("".join(c[0] for c in line) for line in LOGO_CELLS)
# "─term" 은 그림자까지 포함한 로고 맨 아랫줄에 붙여 바닥을 맞춘다
_TAIL_ROW = len(LOGO_CELLS) - 1


def banner(version: str, info: list[str]) -> str:
    width = max(len(line) for line in LOGO)
    out = ["\r\n"]
    for i, cells in enumerate(LOGO_CELLS):
        line = " " + cells_to_ansi(cells)
        if i == _TAIL_ROW:
            line += " " * (width - len(LOGO[i])) + f" {_SUB_STYLE}─term{_RESET}"
        out.append(line + "\r\n")
    out.append("\r\n")
    out.append(f" {_SUB_STYLE}{tr('banner.tagline')} · v{version}{_RESET}\r\n")
    for line in info:
        out.append(f" {_INFO_STYLE}{line}{_RESET}\r\n")
    out.append("\r\n")
    return "".join(out)
