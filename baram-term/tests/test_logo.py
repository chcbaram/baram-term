import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402
from retroui import TerminalScreen  # noqa: E402

from baram_term.icon import make_icon  # noqa: E402
from baram_term.logo import (  # noqa: E402
    GLYPHS,
    LOGO,
    LOGO_CELLS,
    LOGO_GAP,
    SHADOW_OFFSET,
    SHADOW_RGB,
    banner,
    bitmap_to_cells,
    bitmap_to_half_cells,
    word_bitmap,
)

INK, SHADOW = "ink", "shadow"
SHADOW_FG = "38;2;{};{};{}".format(*SHADOW_RGB)
SHADOW_BG = "48;2;{};{};{}".format(*SHADOW_RGB)
KIND = {"97": INK, "107": INK, SHADOW_FG: SHADOW, SHADOW_BG: SHADOW, None: None}


def test_wide_dot_conversion():
    assert bitmap_to_cells(["#.#", ".#."]) == ["██  ██", "  ██"]


def test_half_block_conversion():
    # 열마다 (위 도트, 아래 도트): (#,#)=█  (.,#)=▄  (#,.)=▀ / 홀수 줄은 아래를 빈 도트로 채운다
    assert bitmap_to_half_cells(["#.#", "##.", "..#"]) == ["█▄▀", "  ▀"]


def test_glyphs_have_even_height():
    # 홀수 높이면 반쪽 블록 마지막 줄이 반만 차서 글자가 뭉개진다
    assert all(len(rows) % 2 == 0 for rows in GLYPHS.values())


def test_word_bitmap_has_one_dot_gap():
    rows = word_bitmap("BA")
    assert rows[0] == "#####." + "." + ".####."
    assert all(len(r) == 13 for r in rows)


def decode_dots(lines):
    """셀을 다시 도트 격자로 푼다: (문자, 글자색, 배경색) -> 위/아래 도트 종류."""
    dots = []
    for line in lines:
        top, bottom = [], []
        for ch, fg, bg in line:
            t, b = {"█": (fg, fg), "▀": (fg, bg), "▄": (bg, fg), " ": (None, None)}[ch]
            top.append(KIND[t])
            bottom.append(KIND[b])
        dots += [top, bottom]
    return dots


def test_logo_and_shadow_dots_match_bitmap():
    rows = word_bitmap("BARAM", LOGO_GAP)
    dx, dy = SHADOW_OFFSET
    dots = decode_dots(LOGO_CELLS)
    for y in range(len(rows) + dy):
        for x in range(len(rows[0]) + dx):
            ink = y < len(rows) and x < len(rows[0]) and rows[y][x] == "#"
            sy, sx = y - dy, x - dx
            shadow = 0 <= sy < len(rows) and 0 <= sx < len(rows[0]) and rows[sy][sx] == "#"
            expected = INK if ink else SHADOW if shadow else None
            got = dots[y][x] if x < len(dots[y]) else None
            assert got == expected, (x, y)


def test_logo_size_and_letters_stay_apart():
    assert len(LOGO) == 4  # 글자 6도트 + 그림자 1도트 -> 반쪽 블록 4줄
    assert max(len(line) for line in LOGO) == 5 * 6 + 4 * LOGO_GAP + 1
    # 그림자가 들어가도 글자 사이에 빈 열이 하나 남는다 (B 오른쪽 끝 5, 그림자 6, 빈 열 7)
    rows = word_bitmap("BARAM", LOGO_GAP)
    gap_col = 6 + 1
    assert all(line[gap_col] == " " for line in LOGO[:3] if len(line) > gap_col)


def test_banner_colors_in_terminal_screen():
    screen = TerminalScreen(80, 20)
    screen.feed(banner("0.1.0", []))
    styles = {cell[1] for line in screen.lines for cell in line}
    assert (15, None, 0) in styles  # 로고: 밝은 흰색
    assert (SHADOW_RGB, None, 0) in styles  # 그림자: 트루컬러 어두운 회색
    assert (15, SHADOW_RGB, 0) in styles  # 로고 위 도트 + 그림자 아래 도트가 한 칸에


def test_icon_is_rounded_terminal_window():
    pygame.init()
    icon = make_icon(128)
    assert icon.get_size() == (128, 128)
    assert icon.get_at((0, 0)).a == 0  # 둥근 모서리 바깥은 투명
    assert icon.get_at((64, 64)).a == 255
