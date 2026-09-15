"""README 아키텍처 그림: retro-ui 로 직접 그려서 화면과 같은 화풍으로 PNG 저장.

사용: python docs/images/make_architecture.py docs/images/architecture.png
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "retro-ui", "src"))

from retroui.core.wcwidth import str_width  # noqa: E402
from retroui.render.cellbuffer import CellBuffer  # noqa: E402
from retroui.render.fonts import FontSet  # noqa: E402
from retroui.render.renderer import Renderer  # noqa: E402

BG = (0, 0, 0)
FG = (200, 200, 200)
DIM = (120, 120, 120)
APP = (120, 230, 120)
LIB = (90, 210, 230)
BASE = (230, 200, 110)

# 스크린샷과 셀 크기(14px)·폭(1640px)을 맞춘다: 나란히 놓았을 때 글자가 같은 크기로 보이게
COLS, ROWS = 116, 23
PAD = 1


def box(buf, x, y, w, h, color, title):
    buf.text(x, y, "┌" + "─" * (w - 2) + "┐", color, BG)
    for i in range(1, h - 1):
        buf.text(x, y + i, "│", color, BG)
        buf.text(x + w - 1, y + i, "│", color, BG)
    buf.text(x, y + h - 1, "└" + "─" * (w - 2) + "┘", color, BG)
    buf.text(x + 2, y, " " + title + " ", color, BG)


def note(buf, x, y, w, text):
    """박스 오른쪽 끝에 흐린 글씨로 (경로 같은) 보조 정보."""
    buf.text(x + w - 2 - str_width(text), y, text, DIM, BG)


def rows(buf, x, y, items, label_color):
    """(왼쪽 라벨, 내용) 줄들을 라벨 폭을 맞춰 찍는다."""
    lw = max(str_width(a) for a, _ in items)
    for i, (label, body) in enumerate(items):
        buf.text(x, y + i, label + " " * (lw - str_width(label) + 2), label_color, BG)
        buf.text(x + lw + 2, y + i, body, FG, BG)


def build():
    buf = CellBuffer(COLS, ROWS, FG, BG)
    w = COLS - 2 * PAD
    x = PAD
    y = 0

    buf.text(x, y, "baram-term 은 UI 엔진 retro-ui 를 먼저 만들고 그 위에 올린 앱이다", DIM, BG)
    y += 2

    box(buf, x, y, w, 6, APP, "baram-term · 앱")
    rows(buf, x + 2, y + 1, [
        ("화면", "터미널 · 그래프 패널 · 포트 설정 · 로그 · 찾기 · 메뉴"),
        ("장치", "시리얼 계층 (수신 스레드 · 송신 큐 · 자동 재연결 · 통계)"),
        ("해석", "그래프 줄 파서 (Teleplot / Arduino) · 강조 규칙 · 자동완성"),
        ("설정", "settings.json (포트 · 속도 · 줄끝 코드 · 창 배치 · 명령 목록)"),
    ], APP)
    note(buf, x, y + 1, w, "baram-term/src/baram_term/")
    note(buf, x, y + 4, w, "실행 명령 baram-term")
    y += 6

    mid = x + 10
    buf.text(mid, y, "│", DIM, BG)
    buf.text(mid + 2, y, "import retroui   (라이브러리는 앱을 모른다 · 한 방향)", DIM, BG)
    y += 1

    box(buf, x, y, w, 6, LIB, "retro-ui · UI 엔진")
    rows(buf, x + 2, y + 1, [
        ("위젯", "Terminal · LivePlot · Dialog · Menu · FileDialog · ListView"),
        ("코어", "레이아웃 · 포커스 / 마우스 · 이벤트 루프 · 타이머 · 테마"),
        ("렌더", "셀 버퍼 (바뀐 셀만) · 글리프 캐시 · 박스 문자 · 픽셀 플롯"),
        ("입력", "키 / 마우스 · 클립보드 · 한글 IME 보정 · HiDPI"),
    ], LIB)
    note(buf, x, y + 1, w, "retro-ui/src/retroui/")
    note(buf, x, y + 4, w, "import retroui · 앱과 따로 떼어낼 수 있다")
    y += 6

    buf.text(mid, y, "│", DIM, BG)
    y += 1

    box(buf, x, y, w, 4, BASE, "바탕")
    rows(buf, x + 2, y + 1, [
        ("pygame-ce", "창 · 이벤트 · 폰트 · 서피스 (SDL2)"),
        ("numpy", "플롯 링버퍼 축약"),
    ], BASE)
    note(buf, x, y + 1, w, "pyserial · 시리얼 포트")
    note(buf, x, y + 2, w, "Qt 없음 · OS 기본 대화상자 없음")
    y += 4

    line = "macOS · Windows · Linux  —  같은 코드, 같은 화면"
    buf.text(x + (w - str_width(line)) // 2, y + 1, line, DIM, BG)
    return buf


def main() -> None:
    out = sys.argv[1] if len(sys.argv) > 1 else "architecture.png"
    pygame.init()
    fonts = FontSet("d2coding", 28, 1.0)
    buf = build()
    pad = 8
    surf = pygame.Surface((COLS * fonts.cw + pad * 2, ROWS * fonts.ch + pad * 2))
    surf.fill(BG)
    r = Renderer(fonts, buf)
    r.ox, r.oy = pad, pad
    r.render(surf)
    pygame.image.save(surf, out)
    print("saved", out, surf.get_size())


if __name__ == "__main__":
    main()
