"""P0 spike: 한글 IME 이벤트 순서 기록 (수동 실행).

창에서 한글을 입력하면 KEYDOWN / TEXTEDITING / TEXTINPUT 순서를 콘솔과
JSON 파일로 남긴다. 이 로그는 P3 IME 재생 테스트의 fixture 로 쓴다.

확인할 시나리오 (시나리오마다 F1 을 눌러 로그에 구분 표시):
  1. "안녕하세요 world" 입력
  2. "한" 조합 중 Backspace
  3. "한" 조합 중 Enter
  4. "한" 조합 중 마우스로 창 아래쪽 클릭 (포커스 이동 흉내 -> stop_text_input)
  5. 한/영 전환 후 영문 입력
ESC 또는 창 닫기로 종료.

usage: python examples/spike_ime.py
"""

import json
import os
import time

os.environ.setdefault("SDL_IME_SUPPORT_EXTENDED_TEXT", "1")

import pygame  # noqa: E402
import pygame.freetype  # noqa: E402

OUT_DIR = os.environ.get("SPIKE_OUT", "_spike_out")
FONT_PATH = os.path.expanduser("~/Library/Fonts/D2Coding-Ver1.3.2-20180524-all.ttc")


def main():
  os.makedirs(OUT_DIR, exist_ok=True)
  pygame.init()
  pygame.freetype.init()
  pygame.key.set_repeat(400, 35)

  win = pygame.Window("spike_ime", (760, 300), allow_high_dpi=True)
  surf = win.get_surface()
  scale = surf.get_width() / win.size[0]
  font = pygame.freetype.Font(FONT_PATH, round(18 * scale))
  cw = font.get_metrics("M")[0][4]
  line_h = font.get_sized_height()

  text = ""
  preedit = ""
  text_input_on = True
  log = []
  scenario = 1
  t0 = time.monotonic()

  def rec(kind, **kw):
    item = {"t": round(time.monotonic() - t0, 4), "scenario": scenario, "type": kind, **kw}
    log.append(item)
    print(item)

  pygame.key.start_text_input()
  running = True
  while running:
    for ev in pygame.event.get():
      if ev.type in (pygame.QUIT, pygame.WINDOWCLOSE):
        running = False
      elif ev.type == pygame.TEXTEDITING:
        rec("TEXTEDITING", text=ev.text, start=ev.start, length=ev.length)
        preedit = ev.text
      elif ev.type == pygame.TEXTINPUT:
        rec("TEXTINPUT", text=ev.text)
        text += ev.text
        preedit = ""
      elif ev.type == pygame.KEYDOWN:
        rec("KEYDOWN", key=pygame.key.name(ev.key), mod=ev.mod, unicode=ev.unicode, scancode=ev.scancode)
        if ev.key == pygame.K_ESCAPE:
          running = False
        elif ev.key == pygame.K_F1:
          scenario += 1
          rec("MARK", note=f"scenario {scenario} start")
        elif ev.key == pygame.K_BACKSPACE and not preedit:
          text = text[:-1]
        elif ev.key == pygame.K_RETURN and not preedit:
          text += "⏎"
      elif ev.type == pygame.KEYUP:
        rec("KEYUP", key=pygame.key.name(ev.key))
      elif ev.type == pygame.MOUSEBUTTONDOWN:
        # 창 아래쪽 절반 클릭은 "다른 위젯으로 포커스 이동" 으로 간주해 입력을 끈다/켠다
        if ev.pos[1] > win.size[1] // 2:
          text_input_on = not text_input_on
          if text_input_on:
            pygame.key.start_text_input()
          else:
            pygame.key.stop_text_input()
          rec("MARK", note=f"text_input {'on' if text_input_on else 'off'}", preedit_before=preedit)
          preedit = ""

    surf.fill((0, 0, 170))
    y = int(12 * scale)
    font.render_to(surf, (int(12 * scale), y), f"scenario {scenario}  input={'ON' if text_input_on else 'OFF'}  (F1 next, ESC quit)", (255, 255, 85))
    y += line_h * 2
    x = int(12 * scale)
    font.render_to(surf, (x, y), text, (255, 255, 255))
    x += font.get_rect(text).width if text else 0
    if preedit:
      r = font.render_to(surf, (x, y), preedit, (85, 255, 255))
      pygame.draw.line(surf, (85, 255, 255), (x, y + line_h), (x + r.width, y + line_h), max(1, int(scale)))
      x += r.width
    pygame.draw.rect(surf, (255, 255, 255), (x, y, max(1, int(scale)), line_h))
    pygame.key.set_text_input_rect(pygame.Rect(x / scale, y / scale, cw * 2 / scale, line_h / scale))
    win.flip()
    pygame.time.wait(16)

  out = os.path.join(OUT_DIR, "ime_log.json")
  with open(out, "w", encoding="utf-8") as fp:
    json.dump(log, fp, ensure_ascii=False, indent=1)
  print(f"[OK] saved {out} ({len(log)} events)")
  pygame.quit()


if __name__ == "__main__":
  main()
