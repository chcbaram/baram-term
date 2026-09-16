import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from retroui.render.cellbuffer import CellBuffer  # noqa: E402
from retroui.render.fonts import FontSet  # noqa: E402
from retroui.render.renderer import Renderer  # noqa: E402

FG = (255, 255, 255)
BG = (0, 0, 170)


@pytest.fixture(scope="module")
def fonts():
    # pygame.init() 은 오디오까지 올린다. 사운드 장치가 없는 윈도우 러너에서 그 실패가
    # 8 초를 먹어 이 파일 하나가 스위트에서 가장 느렸다 (App 도 같은 이유로 고쳤다)
    pygame.display.init()
    try:
        f = FontSet("d2coding", 16, 1.0)
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))
    yield f
    pygame.quit()


def render(fonts, cols, text):
    buf = CellBuffer(cols, 1, FG, BG)
    buf.text(0, 0, text, FG, BG)
    surf = pygame.Surface((cols * fonts.cw, fonts.ch))
    rects = Renderer(fonts, buf).render(surf)
    return surf, buf, rects


def lit(surf, x0, x1):
    return sum(1 for x in range(x0, x1) for y in range(surf.get_height()) if surf.get_at((x, y))[:3] != BG)


def test_hangul_cell_is_exactly_two_latin_cells(fonts):
    assert fonts.cw == 8
    glyph = fonts.glyph("한", FG, width=2)
    assert glyph.get_width() == fonts.cw * 2


def test_horizontal_box_line_has_no_gaps(fonts):
    surf, _, _ = render(fonts, 4, "────")
    cy = fonts.ch // 2
    assert all(surf.get_at((x, cy))[:3] == FG for x in range(4 * fonts.cw))


def test_corner_joins_vertical_line(fonts):
    buf = CellBuffer(1, 2, FG, BG)
    buf.text(0, 0, "┌", FG, BG)
    buf.text(0, 1, "│", FG, BG)
    surf = pygame.Surface((fonts.cw, fonts.ch * 2))
    Renderer(fonts, buf).render(surf)
    cx = fonts.cw // 2
    assert all(surf.get_at((cx, y))[:3] == FG for y in range(fonts.ch // 2 + 1, fonts.ch * 2))


def test_hangul_glyph_stays_in_its_two_cells(fonts):
    surf, _, _ = render(fonts, 3, "한")
    assert lit(surf, 0, fonts.cw) > 0
    assert lit(surf, fonts.cw, fonts.cw * 2) > 0
    assert lit(surf, fonts.cw * 2, fonts.cw * 3) == 0


def test_lower_half_block(fonts):
    surf, _, _ = render(fonts, 1, "▄")
    assert surf.get_at((fonts.cw // 2, 0))[:3] == BG
    assert surf.get_at((fonts.cw // 2, fonts.ch - 1))[:3] == FG


def test_only_changed_cells_are_redrawn(fonts):
    buf = CellBuffer(5, 1, FG, BG)
    surf = pygame.Surface((5 * fonts.cw, fonts.ch))
    r = Renderer(fonts, buf)
    assert r.render(surf) == [pygame.Rect(0, 0, 5 * fonts.cw, fonts.ch)]
    buf.put(1, 0, "x", FG, BG)
    assert r.render(surf) == [pygame.Rect(fonts.cw, 0, fonts.cw, fonts.ch)]
    assert r.render(surf) == []


def test_missing_glyph_does_not_crash(fonts):
    surf, _, _ = render(fonts, 2, "\U0001f600")  # 이모지: 주 폰트에 없음 -> fallback 또는 두부
    assert lit(surf, 0, 2 * fonts.cw) > 0
