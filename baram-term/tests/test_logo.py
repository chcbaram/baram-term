import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

from baram_term.icon import make_icon  # noqa: E402
from baram_term.logo import GLYPHS, LOGO, bitmap_to_cells, bitmap_to_half_cells, word_bitmap  # noqa: E402


def test_wide_dot_conversion():
    assert bitmap_to_cells(["#.#", ".#."]) == ["██  ██", "  ██"]


def test_half_block_conversion():
    # 열마다 (위 도트, 아래 도트): (#,#)=█  (.,#)=▄  (#,.)=▀ / 홀수 줄은 아래를 빈 도트로 채운다
    assert bitmap_to_half_cells(["#.#", "##.", "..#"]) == ["█▄▀", "  ▀"]


def test_word_bitmap_has_one_dot_gap():
    rows = word_bitmap("BA")
    assert rows[0] == "####." + "." + ".###."
    assert all(len(r) == 11 for r in rows)


def test_logo_size_and_r_has_straight_leg():
    assert len(LOGO) == 5
    assert max(len(line) for line in LOGO) == 5 * 5 * 2 + 4 * 2
    assert GLYPHS["R"][3:] == ("#...#", "#...#")
    # R 은 세 번째 글자: 도트 x 12..16 -> 칸 24..33
    r_bottom = LOGO[4][24:34]
    assert r_bottom == "██      ██"


def test_icon_is_rounded_terminal_window():
    pygame.init()
    icon = make_icon(128)
    assert icon.get_size() == (128, 128)
    assert icon.get_at((0, 0)).a == 0  # 둥근 모서리 바깥은 투명
    assert icon.get_at((64, 64)).a == 255
