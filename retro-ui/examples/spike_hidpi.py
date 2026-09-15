"""P0 spike: macOS HiDPI 동작 확인.

창 크기(point)와 윈도우 서피스 크기(pixel)를 비교해 실제 2x 서피스가 나오는지 본다.
서피스가 point 크기로 나오면 Renderer/Texture 경로를 fallback 으로 써야 한다.

usage: python examples/spike_hidpi.py [seconds]
"""

import os
import sys
import time

import pygame

OUT_DIR = os.environ.get("SPIKE_OUT", "_spike_out")


def probe_renderer():
  # 같은 창에 surface 와 renderer 를 동시에 쓸 수 없으므로 별도 창에서 확인
  try:
    from pygame._sdl2.video import Renderer, Window

    win = Window("spike_hidpi_renderer", size=(480, 320), allow_high_dpi=True)
    ren = Renderer(win)
    vp = ren.get_viewport()
    print(f"[renderer] window size (pt): {win.size}, viewport (px): {vp}")
    win.destroy()
  except Exception as e:  # noqa: BLE001 - 스파이크라 원인만 출력
    print(f"[renderer] probe failed: {e!r}")


def main():
  seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0
  os.makedirs(OUT_DIR, exist_ok=True)

  pygame.init()
  win = pygame.Window("spike_hidpi", (480, 320), allow_high_dpi=True, resizable=True)
  surf = win.get_surface()

  scale = surf.get_width() / win.size[0]
  print(f"[surface] window size (pt) : {win.size}")
  print(f"[surface] surface size (px): {surf.get_size()}")
  print(f"[surface] scale            : {scale:.2f}")
  print(f"[display] desktop sizes    : {pygame.display.get_desktop_sizes()}")

  # 1px 체커보드: 2x 서피스면 Retina 에서 선명한 미세 격자로 보여야 한다
  w, h = surf.get_size()
  surf.fill((0, 0, 170))
  for y in range(0, h // 2):
    for x in range(0, w // 2):
      if (x + y) & 1:
        surf.set_at((x, y), (255, 255, 255))
  pygame.draw.rect(surf, (255, 255, 0), (w // 2, h // 2, w // 2 - 1, h // 2 - 1), 1)
  pygame.image.save(surf, os.path.join(OUT_DIR, "hidpi.png"))

  t_end = time.monotonic() + seconds
  resized = []
  while time.monotonic() < t_end:
    for ev in pygame.event.get():
      if ev.type in (pygame.QUIT, pygame.WINDOWCLOSE):
        t_end = 0
      elif ev.type == pygame.WINDOWSIZECHANGED:
        surf = win.get_surface()
        resized.append((win.size, surf.get_size()))
    win.flip()
    pygame.time.wait(16)

  for pt, px in resized:
    print(f"[resize] pt={pt} px={px}")
  win.destroy()

  probe_renderer()
  pygame.quit()


if __name__ == "__main__":
  main()
