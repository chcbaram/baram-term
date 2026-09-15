"""README 스크린샷: demo:// 가짜 펌웨어에 붙어 터미널 + 그래프를 그린 뒤 PNG 로 저장.

사용: python docs/images/make_screenshot.py docs/images/screenshot.png [ko|en]
창을 띄우지 않고 (SDL_VIDEODRIVER=dummy) 15초쯤 실제로 돌린 뒤 그 화면을 그대로 저장한다.
"""
import os, sys, time
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.join(ROOT, "baram-term", "src"))
sys.path.insert(0, os.path.join(ROOT, "retro-ui", "src"))

from baram_term.app import BaramTerm
from baram_term.serial_port import DEMO_PORT, PortSettings
from baram_term.settings import Settings

out = sys.argv[1]
lang = sys.argv[2] if len(sys.argv) > 2 else "ko"
from baram_term import i18n
i18n.set_language(lang)
import retroui
retroui.set_language(lang)

cfg = Settings(port=DEMO_PORT, plot=True, plot_window=10.0, plot_split=2 / 3, plot_hide_lines=True)
term = BaramTerm(PortSettings(DEMO_PORT, 115200), size=(116, 34), font_size=28, headless=True, config=cfg)
term.connect()

def pump(seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        term.app.step()
        time.sleep(0.01)

def type_line(text):
    for ch in text:
        term.send(ch.encode())
        pump(0.02)
    term.send(b"\r")
    pump(0.5)

pump(1.0)
type_line("help")
type_line("info")
type_line("plot")
# 켠 뒤로는 입력하지 않는다: 그래프 줄이 터미널에서 깨끗하게 빠진 모습이 남는다
pump(11.5)

term.app.invalidate()   # 전체 다시 그리기 (부분 갱신에서 줄 끝 한글이 빠지는 문제 회피)
term.app.step()
pygame.image.save(term.app.surface, out)
print("saved", out, term.app.surface.get_size())
