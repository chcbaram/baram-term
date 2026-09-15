"""P0 spike: 폰트 셀 메트릭과 한글 폭 비율 확인.

각 폰트로 영문 advance, 한글 advance, 줄 높이를 재고, 문자열 흐름 렌더링과
셀 격자 배치 렌더링을 나란히 PNG 로 저장해 정렬/박스 문자 틈을 눈으로 비교한다.

usage: python examples/spike_font.py
"""

import os
import unicodedata

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402
import pygame.freetype  # noqa: E402

OUT_DIR = os.environ.get("SPIKE_OUT", "_spike_out")
HOME_FONTS = os.path.expanduser("~/Library/Fonts")

FONTS = [
  ("D2Coding", os.path.join(HOME_FONTS, "D2Coding-Ver1.3.2-20180524-all.ttc"), 0, True),
  ("D2Coding#1", os.path.join(HOME_FONTS, "D2Coding-Ver1.3.2-20180524-all.ttc"), 1, True),
  ("DungGeunMo", os.path.join(HOME_FONTS, "DungGeunMo.ttf"), 0, False),
  ("AppleSDGothicNeo", "/System/Library/Fonts/AppleSDGothicNeo.ttc", 0, True),
  ("Menlo", "/System/Library/Fonts/Menlo.ttc", 0, True),
]
SIZES = [16, 32]
SAMPLE = "AMW_ 012 가나다 한글 ┌─┬─┐│┼ ░▒▓█▁▄ °±µΩ"


def cell_width(ch):
  if unicodedata.east_asian_width(ch) in ("W", "F"):
    return 2
  return 1


def advance(font, ch):
  m = font.get_metrics(ch)
  if not m or m[0] is None:
    return None
  return m[0][4]


def main():
  os.makedirs(OUT_DIR, exist_ok=True)
  pygame.init()
  pygame.freetype.init()

  rows = []
  for name, path, index, aa in FONTS:
    if not os.path.exists(path):
      print(f"[skip] {name}: {path} not found")
      continue
    for size in SIZES:
      try:
        f = pygame.freetype.Font(path, size, font_index=index)
      except Exception as e:  # noqa: BLE001
        print(f"[E_] {name}#{index} size={size}: {e!r}")
        continue
      f.antialiased = aa
      f.pad = False
      f.origin = True
      adv_m = max(advance(f, c) or 0 for c in "0MW_")
      adv_ko = advance(f, "가")
      line_h = f.get_sized_height()
      missing = [c for c in SAMPLE if c != " " and advance(f, c) is None]
      ratio = (adv_ko / adv_m) if adv_ko and adv_m else None
      print(
        f"[font] {f.name!r:28} idx={index} size={size:2d} "
        f"cell={adv_m:.2f}x{line_h} ko_adv={adv_ko} "
        f"ratio={ratio if ratio is None else round(ratio, 3)} "
        f"asc={f.get_sized_ascender()} desc={f.get_sized_descender()} "
        f"missing={''.join(missing)!r}"
      )
      rows.append((name, f, adv_m, line_h))

  # 렌더링 비교 이미지: 폰트별로 [흐름 렌더링] / [셀 격자 배치] 두 줄
  pad = 8
  label_font = pygame.freetype.SysFont(None, 14)
  img_w = 1400
  img_h = sum(r[3] * 2 + 28 for r in rows) + pad
  img = pygame.Surface((img_w, img_h))
  img.fill((0, 0, 120))

  y = pad
  for name, f, adv_m, line_h in rows:
    label_font.render_to(img, (pad, y), f"{name} {f.size}px cell={adv_m:.1f}x{line_h}", (255, 255, 0))
    y += 20

    f.render_to(img, (pad, y + f.get_sized_ascender()), SAMPLE, (255, 255, 255))
    y += line_h

    cw = max(1, round(adv_m))
    col = 0
    for ch in SAMPLE:
      w = cell_width(ch)
      if (col // 1) % 2 == 0:
        pygame.draw.rect(img, (0, 0, 160), (pad + col * cw, y, cw * w, line_h))
      if ch != " ":
        rect = f.get_rect(ch)
        gx = pad + col * cw + (cw * w - rect.width) // 2 if w == 2 else pad + col * cw
        f.render_to(img, (gx, y + f.get_sized_ascender()), ch, (170, 255, 170))
      col += w
    y += line_h + 8

  out = os.path.join(OUT_DIR, "fonts.png")
  pygame.image.save(img, out)
  print(f"[OK] saved {out}")
  pygame.quit()


if __name__ == "__main__":
  main()
