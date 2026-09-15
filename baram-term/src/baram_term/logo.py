"""Start-up banner shown in the terminal (not sent to the device).

로고 글자는 5x5 도트 비트맵으로 정의하고, 도트 1개를 가로 2칸 x 세로 1줄("██")로 그린다.
D2Coding 셀은 가로:세로가 약 8:19 라 2칸이면 거의 정사각형 도트가 된다.
반쪽 블록(▀▄)으로 세로 2도트를 한 줄에 묶으면 로고가 작아지고, 줄 경계에서 R 다리 같은 모양이 뭉개졌다.
블록 문자는 retro-ui 가 폰트 대신 도형으로 그려서 칸 사이 틈 없이 이어진다.
"""

from __future__ import annotations

from baram_term.i18n import tr

# 모서리를 깎은 굵은 도트 글꼴 (chcbaram 로고의 BARAM 글자 모양을 따름)
GLYPHS: dict[str, tuple[str, ...]] = {
    "B": (
        "####.",
        "#...#",
        "####.",
        "#...#",
        "####.",
    ),
    "A": (
        ".###.",
        "#...#",
        "#####",
        "#...#",
        "#...#",
    ),
    # 대각선 다리는 도트가 적어 R 로 읽히지 않는다: 오른쪽 다리를 곧게 내린다
    "R": (
        "####.",
        "#...#",
        "####.",
        "#...#",
        "#...#",
    ),
    "M": (
        "##.##",
        "#.#.#",
        "#.#.#",
        "#...#",
        "#...#",
    ),
}

_HALF = {(True, True): "█", (True, False): "▀", (False, True): "▄", (False, False): " "}


def word_bitmap(word: str, gap: int = 1) -> list[str]:
    height = max(len(GLYPHS[c]) for c in word)
    rows = []
    for y in range(height):
        parts = [GLYPHS[c][y] if y < len(GLYPHS[c]) else "." * len(GLYPHS[c][0]) for c in word]
        rows.append(("." * gap).join(parts))
    return rows


def bitmap_to_cells(rows: list[str]) -> list[str]:
    """'#' 도트 1개 = "██" (가로 2칸 x 세로 1줄)."""
    return ["".join("██" if ch == "#" else "  " for ch in row).rstrip() for row in rows]


def bitmap_to_half_cells(rows: list[str]) -> list[str]:
    """'#' 도트 비트맵을 반쪽 블록 문자로 (가로 1칸 x 세로 2도트). 작은 그림용."""
    width = max((len(r) for r in rows), default=0)
    grid = [r.ljust(width, ".") for r in rows]
    if len(grid) % 2:
        grid.append("." * width)
    out = []
    for y in range(0, len(grid), 2):
        top, bottom = grid[y], grid[y + 1]
        out.append("".join(_HALF[(top[x] == "#", bottom[x] == "#")] for x in range(width)).rstrip())
    return out


LOGO = tuple(bitmap_to_cells(word_bitmap("BARAM")))

_RESET = "\x1b[0m"
_LOGO_STYLE = "\x1b[1;97m"  # 굵은 흰색
_SUB_STYLE = "\x1b[0;37m"  # 밝은 회색
_INFO_STYLE = "\x1b[0;90m"  # 어두운 회색


def banner(version: str, info: list[str]) -> str:
    width = max(len(line) for line in LOGO)
    out = ["\r\n"]
    for i, line in enumerate(LOGO):
        tail = f"{' ' * (width - len(line))}  {_SUB_STYLE}─term" if i == len(LOGO) - 1 else ""
        out.append(f" {_LOGO_STYLE}{line}{tail}{_RESET}\r\n")
    out.append("\r\n")
    out.append(f" {_SUB_STYLE}{tr('banner.tagline')} · v{version}{_RESET}\r\n")
    for line in info:
        out.append(f" {_INFO_STYLE}{line}{_RESET}\r\n")
    out.append("\r\n")
    return "".join(out)
