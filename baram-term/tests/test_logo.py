import io
import os
import struct

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402
from retroui import TerminalScreen  # noqa: E402

from baram_term.icon import icns_bytes, ico_bytes, make_icon  # noqa: E402
from baram_term.logo import (  # noqa: E402
    INK_RGB,
    LOGO,
    LOGO_CELLS,
    LOGO_DOTS,
    SHADOW_OFFSET,
    SHADOW_RGB,
    banner,
    bitmap_to_cells,
    bitmap_to_half_cells,
)

INK, SHADOW = "ink", "shadow"
SHADOW_FG = "38;2;{};{};{}".format(*SHADOW_RGB)
SHADOW_BG = "48;2;{};{};{}".format(*SHADOW_RGB)
INK_FG = "38;2;{};{};{}".format(*INK_RGB)
INK_BG = "48;2;{};{};{}".format(*INK_RGB)
KIND = {INK_FG: INK, INK_BG: INK, SHADOW_FG: SHADOW, SHADOW_BG: SHADOW, None: None}


def test_wide_dot_conversion():
    assert bitmap_to_cells(["#.#", ".#."]) == ["██  ██", "  ██"]


def test_half_block_conversion():
    # 열마다 (위 도트, 아래 도트): (#,#)=█  (.,#)=▄  (#,.)=▀ / 홀수 줄은 아래를 빈 도트로 채운다
    assert bitmap_to_half_cells(["#.#", "##.", "..#"]) == ["█▄▀", "  ▀"]


def test_logo_plus_shadow_height_fills_whole_rows():
    # 전체 도트 높이가 홀수면 반쪽 블록 마지막 줄이 반만 차서 아래쪽이 뭉개진다
    assert (len(LOGO_DOTS) + SHADOW_OFFSET[1]) % 2 == 0


def test_logo_dots_are_a_rectangular_grid_of_two_symbols():
    assert len(set(len(row) for row in LOGO_DOTS)) == 1
    assert set("".join(LOGO_DOTS)) == {"#", "."}


def test_logo_is_an_integer_downscale_of_the_source():
    # 정수 배율(2배)이라야 A, M 처럼 대칭인 글자가 대칭으로 남는다. 126x24 -> 63x12 (+ 빈 줄 1)
    assert len(LOGO_DOTS[0]) == 126 // 2
    assert len(LOGO_DOTS) == 24 // 2 + 1


def test_symmetric_letters_stay_symmetric():
    """A 와 M 은 좌우 대칭이다. 어중간한 배율로 줄이면 여기서 깨진다."""
    columns = [any(row[x] == "#" for row in LOGO_DOTS) for x in range(len(LOGO_DOTS[0]))]
    groups, start = [], None
    for x, filled in enumerate(columns):
        if filled and start is None:
            start = x
        elif not filled and start is not None:
            groups.append((start, x - 1))
            start = None
    if start is not None:
        groups.append((start, len(columns) - 1))
    assert len(groups) == 5, "BARAM 다섯 글자로 나뉘어야 한다"
    for letter, (a, b) in zip("BARAM", groups):
        if letter not in ("A", "M"):
            continue
        block = [row[a : b + 1] for row in LOGO_DOTS]
        assert block == [row[::-1] for row in block], letter


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
    rows = list(LOGO_DOTS)
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


def test_logo_cell_size_follows_the_dot_grid():
    dx, dy = SHADOW_OFFSET
    assert len(LOGO) == (len(LOGO_DOTS) + dy) // 2
    assert max(len(line) for line in LOGO) == len(LOGO_DOTS[0]) + dx


def test_logo_fits_the_default_window_width():
    # 기본 창은 100칸. 배너가 줄바꿈되면 "─term" 이 다음 줄로 밀린다
    assert max(len(line) for line in LOGO) + len(" ─term") <= 100


def test_banner_colors_in_terminal_screen():
    screen = TerminalScreen(80, 20)
    screen.feed(banner("0.1.0", []))
    styles = {cell[1] for line in screen.lines for cell in line}
    assert (INK_RGB, None, 0) in styles  # 로고: 순백보다 살짝 낮춘 흰색
    assert (SHADOW_RGB, None, 0) in styles  # 그림자: 어두운 회색
    assert (INK_RGB, SHADOW_RGB, 0) in styles  # 로고 위 도트 + 그림자 아래 도트가 한 칸에


def test_icon_is_rounded_terminal_window():
    # 아이콘은 Surface 에 도형만 그린다. pygame.init() 은 오디오까지 올려서 사운드 장치가
    # 없는 윈도우 러너에서 8 초를 먹었다 (baram-term 스위트에서 가장 느린 테스트였다)
    pygame.display.init()
    icon = make_icon(128)
    assert icon.get_size() == (128, 128)
    assert icon.get_at((0, 0)).a == 0  # 둥근 모서리 바깥은 투명
    assert icon.get_at((64, 64)).a == 255


def _png_size(png):
    assert png.startswith(b"\x89PNG")
    return pygame.image.load(io.BytesIO(png), "icon.png").get_size()


def test_icns_holds_a_png_per_size():
    pygame.display.init()
    data = icns_bytes()
    assert data[:4] == b"icns"
    assert struct.unpack(">I", data[4:8])[0] == len(data)
    sizes, pos = {}, 8
    while pos < len(data):
        kind, length = struct.unpack(">4sI", data[pos : pos + 8])
        sizes[kind] = _png_size(data[pos + 8 : pos + length])
        pos += length
    assert pos == len(data)
    assert sizes[b"ic07"] == (128, 128)
    assert sizes[b"ic10"] == (1024, 1024)


def test_ico_directory_points_at_each_png():
    pygame.display.init()
    data = ico_bytes()
    reserved, kind, count = struct.unpack("<HHH", data[:6])
    assert (reserved, kind) == (0, 1)
    sides = []
    for i in range(count):
        w, h, _, _, _, bpp, length, offset = struct.unpack("<BBBBHHII", data[6 + 16 * i : 22 + 16 * i])
        assert bpp == 32
        side = w or 256
        assert _png_size(data[offset : offset + length]) == (side, side)
        sides.append(side)
    assert 16 in sides and 256 in sides
