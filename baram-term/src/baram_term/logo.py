"""Start-up banner shown in the terminal (not sent to the device).

로고는 원본 이미지(`assets/baram-logo.png`)를 도트 격자로 줄여 두고, 반쪽 블록 문자(▀ ▄ █)로
셀 1칸 = 가로 1도트 x 세로 2도트로 그린다.
- 크기를 바꾸려면 `tools/logo_from_image.py <도트 높이>` 를 돌려 LOGO_DOTS 를 다시 만든다.
  실행할 때마다 이미지를 읽지 않으려고 결과를 값으로 박아 둔다 (PyInstaller 로 묶을 때도 편하다).
- 원본 왼쪽 **마크는 쓰지 않고 "BARAM" 글자만** 쓴다. 마크는 선이 가늘어서 도트로 줄이면 선이 끊겨
  깨져 보였다 (17도트 이상이면 살지만 배너가 74칸으로 커진다). 글자는 획이 굵어 작게 줄여도 버틴다.
- 줄일 때 배율은 **정수**로만 잡는다 (지금은 2배: 126x24 픽셀 -> 63x12 도트). 도트 1개가 원본 픽셀
  2x2 에 딱 맞아야 A, M 처럼 좌우 대칭인 글자가 대칭으로 남는다. 2.18픽셀처럼 어중간하게 줄이면
  같은 굵기의 획이 3도트/4도트로 갈려 글자가 비뚤어 보인다 (실제로 보고 확인).
- 전체 도트 줄 수는 그림자 1도트를 더해 짝수여야 반쪽 블록 줄에 딱 맞는다. 모자라면 도구가 맨 위에
  빈 줄을 하나 넣는다 (지금 13줄 = 빈 줄 1 + 글자 12). 홀수면 마지막 줄이 반만 차서 아래가 뭉개진다.
- D2Coding 셀은 가로:세로가 약 8:19 라 반쪽 블록 도트가 거의 정사각형이고, 원본 로고 비율이 그대로 산다.
- 전체 높이(로고 + 그림자 1도트)는 짝수여야 한다. 홀수면 마지막 줄이 반만 차서 아래쪽이 뭉개진다.
- 오른쪽 아래 1도트 그림자를 깔아 흰 글자가 검은 배경에서 덜 튀게 한다. 셀 하나에는 도트가 2개뿐이라
  (로고, 그림자, 배경) 중 최대 두 색만 필요하고, 반쪽 블록의 글자색/배경색으로 표현된다.
블록 문자는 retro-ui 가 폰트 대신 도형으로 그려서 칸 사이 틈 없이 이어진다.
"""

from __future__ import annotations

from baram_term.i18n import tr

# baram-logo.png 글자 부분 126x24 를 2배 줄임 -> 63 x 13 도트
LOGO_DOTS = (
    "...............................................................",
    "##########......######....##########......#####.....###.....###",
    "###########....########...###########....#######....####...####",
    "####....####...###..###...###.....####..####.####...#####.#####",
    "####....####..####..####..###.....####.####...####..###########",
    "####....####.####....####.###.....####.###.....###..###########",
    "##########...####....####.##########...###.....###..###.###.###",
    "##########...####....####.##########...###.....###..###.###.###",
    "####....####.############.###.....####.###########..###.....###",
    "####....####.############.###.....####.###########..###.....###",
    "####....####.####....####.###.....####.###.....###..###.....###",
    "###########..####....####.###.....####.###.....###..###.....###",
    "##########...####....####.###.....####.###.....###..###.....###",
)

SHADOW_OFFSET = (1, 1)  # (오른쪽, 아래) 도트
SHADOW_RGB = (60, 60, 60)
# 순백(ANSI 15)은 검은 배경에서 너무 쨍해서 살짝 낮춘다
INK_RGB = (205, 205, 205)

_EMPTY, _SHADOW, _INK = 0, 1, 2
# SGR 색 코드: 로고와 그림자 모두 트루컬러
_FG = {_EMPTY: None, _SHADOW: "38;2;{};{};{}".format(*SHADOW_RGB), _INK: "38;2;{};{};{}".format(*INK_RGB)}
_BG = {_EMPTY: None, _SHADOW: "48;2;{};{};{}".format(*SHADOW_RGB), _INK: "48;2;{};{};{}".format(*INK_RGB)}
_HALF = {(True, True): "█", (True, False): "▀", (False, True): "▄", (False, False): " "}

Cell = tuple[str, "str | None", "str | None"]  # (문자, 글자색 SGR, 배경색 SGR)


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

LOGO_CELLS = shaded_cells(compose_shadow(list(LOGO_DOTS), *SHADOW_OFFSET))
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
