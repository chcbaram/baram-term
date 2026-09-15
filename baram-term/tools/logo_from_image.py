"""로고 이미지(PNG)를 도트 격자로 바꿔 logo.py 의 LOGO_DOTS 에 넣을 문자열을 찍는다.

    python baram-term/tools/logo_from_image.py [축소 배율]

원본은 `src/baram_term/assets/baram-logo.png` (흑백 1비트). 배율은 **정수**로만 받는다:
도트 1개가 원본 픽셀 N x N 에 딱 맞아야 A, M 처럼 좌우 대칭인 글자가 대칭으로 남는다.
2.18 픽셀처럼 어중간하게 줄이면 같은 굵기의 획이 3도트/4도트로 갈려 글자가 비뚤어 보인다.
결과를 logo.py 의 LOGO_DOTS 에 붙여 넣는다 (실행할 때마다 이미지를 읽지 않게 값으로 박아 둔다).

원본 왼쪽 마크는 쓰지 않는다 (CROP). 마크는 선이 가늘어서 도트로 줄이면 선이 끊겨 깨져 보였다.
글자는 획이 굵어 잘 버틴다. 마크까지 넣으려면 17도트 이상이어야 하는데 그러면 배너가 너무 커진다.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

IMAGE = Path(__file__).resolve().parent.parent / "src" / "baram_term" / "assets" / "baram-logo.png"
COVERAGE = 0.45  # 한 도트 안에서 이만큼 이상 차 있으면 켜진 도트로 본다
# 원본에서 "BARAM" 글자만 (마크와 글자 사이 빈 열 11칸으로 나뉜다).
# 폭/높이는 배율로 나누어떨어지게 잡는다 (왼쪽 빈 열 1px 을 넣어 126 으로 맞췄다)
CROP = (46, 16, 126, 24)  # x, y, 폭, 높이
SCALE = 2


def to_dots(surface: pygame.Surface, dots_h: int, coverage: float = COVERAGE) -> list[str]:
    w, h = surface.get_size()
    dots_w = round(w * dots_h / h)
    rows = []
    for gy in range(dots_h):
        y0, y1 = int(gy * h / dots_h), max(int(gy * h / dots_h) + 1, int((gy + 1) * h / dots_h))
        row = []
        for gx in range(dots_w):
            x0, x1 = int(gx * w / dots_w), max(int(gx * w / dots_w) + 1, int((gx + 1) * w / dots_w))
            total = ink = 0
            for y in range(y0, y1):
                for x in range(x0, x1):
                    r, g, b, a = surface.get_at((x, y))
                    total += 1
                    if a > 128 and (r + g + b) / 3 > 128:
                        ink += 1
            row.append("#" if total and ink / total >= coverage else ".")
        rows.append("".join(row))
    return rows


def main() -> None:
    scale = int(sys.argv[1]) if len(sys.argv) > 1 else SCALE
    pygame.init()
    pygame.display.set_mode((1, 1))
    image = pygame.image.load(str(IMAGE)).convert_alpha()
    text = image.subsurface(pygame.Rect(*CROP)).copy()
    w, h = text.get_size()
    if w % scale or h % scale:
        raise SystemExit(f"CROP {w}x{h} 이 배율 {scale} 로 나누어떨어지지 않는다 (대칭이 깨진다)")
    rows = to_dots(text, h // scale)
    # 그림자 1도트를 더해 짝수 줄이 되어야 반쪽 블록에 딱 맞는다. 모자라면 위에 빈 줄을 하나 넣는다
    if (len(rows) + 1) % 2:
        rows = ["." * len(rows[0])] + rows
    print(f"# {IMAGE.name} 글자 부분 {w}x{h} 를 {scale}배 줄임 -> {len(rows[0])} x {len(rows)} 도트")
    print("LOGO_DOTS = (")
    for row in rows:
        print(f'    "{row}",')
    print(")")


if __name__ == "__main__":
    main()
